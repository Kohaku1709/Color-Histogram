import os
import glob
import time
import hashlib
import json
import numpy as np
from PIL import Image
from .extractor import ColorHistogramExtractor
from .metrics import DistanceMetrics

class DatasetIndexer:
    """
    Quản lý nạp bộ dữ liệu ảnh từ thư mục, kiểm tra tính hợp lệ,
    trích xuất Color Histogram và lưu trữ bộ nhớ đệm (cache) để tái sử dụng.
    """

    VALID_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'}

    def __init__(self, cache_dir='index_cache'):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Dữ liệu index đang nạp trong bộ nhớ
        self.dataset_dir = None
        self.config_id = None
        self.features = None        # shape (N, D) float32
        self.image_paths = []       # danh sách đường dẫn tuyệt đối
        self.rel_paths = []         # danh sách đường dẫn tương đối
        self.categories = []        # danh mục (tên thư mục con nếu có)
        self.image_info = []        # thông tin kích thước, dung lượng
        self.metadata = {}

    def get_cache_filename(self, dataset_dir, color_space, hist_type, bins):
        """
        Tạo tên file cache duy nhất dựa trên đường dẫn dataset và cấu hình trích xuất.
        """
        norm_dir = os.path.abspath(dataset_dir).lower()
        dir_hash = hashlib.md5(norm_dir.encode('utf-8')).hexdigest()[:10]
        bins_str = "_".join(str(b) for b in bins) if hasattr(bins, '__iter__') else str(bins)
        filename = f"index_{dir_hash}_{color_space}_{hist_type}_{bins_str}.npz"
        return os.path.join(self.cache_dir, filename)

    def scan_dataset_files(self, dataset_dir):
        """
        Quét tất cả các file ảnh hợp lệ trong thư mục (kể cả thư mục con).
        Ghi nhận danh mục dựa trên tên thư mục con nếu có.
        """
        dataset_dir = os.path.abspath(dataset_dir)
        if not os.path.exists(dataset_dir):
            return [], []

        raw_files = []
        for root, _, files in os.walk(dataset_dir):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in self.VALID_EXTENSIONS:
                    raw_files.append(os.path.join(root, f))

        raw_files.sort()
        return raw_files

    def validate_image(self, file_path):
        """
        Kiểm tra tính toàn vẹn của file ảnh.
        Trả về (is_valid, width, height, file_size_bytes, error_message).
        """
        try:
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return False, 0, 0, 0, "File dung lượng 0 bytes"

            # Kiểm tra đọc ảnh với Pillow
            with Image.open(file_path) as img:
                img.verify()

            # Mở lại để lấy kích thước và kiểm tra kênh màu
            with Image.open(file_path) as img:
                width, height = img.size
                if width <= 0 or height <= 0:
                    return False, 0, 0, file_size, "Kích thước ảnh không hợp lệ"
                
            return True, width, height, file_size, None
        except Exception as e:
            return False, 0, 0, 0, f"Lỗi đọc file: {str(e)}"

    def build_index(self, dataset_dir, color_space='HSV', hist_type='3d', bins=(8, 8, 8), 
                    force_rebuild=False, progress_callback=None):
        """
        Nạp hoặc trích xuất đặc trưng Color Histogram cho toàn bộ dataset.
        Tự động dùng cache nếu đã trích xuất trước đó.
        """
        dataset_dir = os.path.abspath(dataset_dir)
        cache_path = self.get_cache_filename(dataset_dir, color_space, hist_type, bins)

        # Kiểm tra xem đã có cache chưa và không ép buộc tạo lại
        if not force_rebuild and os.path.exists(cache_path):
            try:
                loaded = self.load_cache(cache_path)
                if loaded:
                    return {
                        'status': 'loaded_from_cache',
                        'message': f'Đã nạp chỉ mục từ bộ nhớ đệm: {os.path.basename(cache_path)}',
                        'total_images': len(self.image_paths),
                        'feature_dim': self.features.shape[1] if self.features is not None else 0,
                        'cache_file': cache_path,
                        'metadata': self.metadata
                    }
            except Exception as e:
                # Nếu cache lỗi, tiến hành quét và trích xuất lại
                pass

        # Bắt đầu quét và kiểm tra
        start_time = time.time()
        candidate_files = self.scan_dataset_files(dataset_dir)
        if not candidate_files:
            return {
                'status': 'error',
                'message': f'Không tìm thấy file ảnh hợp lệ nào trong thư mục: {dataset_dir}',
                'total_scanned': 0,
                'total_valid': 0
            }

        extractor = ColorHistogramExtractor(
            color_space=color_space,
            hist_type=hist_type,
            bins=bins,
            normalize=True
        )

        valid_paths = []
        valid_rel_paths = []
        valid_categories = []
        valid_info = []
        feature_list = []
        corrupted_files = []

        total_files = len(candidate_files)

        for idx, file_path in enumerate(candidate_files):
            if progress_callback:
                progress_callback(idx + 1, total_files, file_path)

            is_valid, w, h, size_bytes, err = self.validate_image(file_path)
            if not is_valid:
                corrupted_files.append({'path': file_path, 'reason': err})
                continue

            feat = extractor.extract(file_path)
            if feat is None:
                corrupted_files.append({'path': file_path, 'reason': 'Không trích xuất được histogram'})
                continue

            # Xác định danh mục dựa trên thư mục con
            rel_path = os.path.relpath(file_path, dataset_dir)
            parts = rel_path.split(os.sep)
            category = parts[0] if len(parts) > 1 else 'Chung'

            valid_paths.append(file_path)
            valid_rel_paths.append(rel_path.replace('\\', '/'))
            valid_categories.append(category)
            valid_info.append({
                'width': w,
                'height': h,
                'size_kb': round(size_bytes / 1024, 1),
                'filename': os.path.basename(file_path)
            })
            feature_list.append(feat)

        if not feature_list:
            return {
                'status': 'error',
                'message': 'Không có ảnh nào trích xuất thành công.',
                'corrupted_files': corrupted_files
            }

        # Lưu vào thuộc tính đối tượng
        self.dataset_dir = dataset_dir
        self.features = np.vstack(feature_list).astype(np.float32)
        self.image_paths = valid_paths
        self.rel_paths = valid_rel_paths
        self.categories = valid_categories
        self.image_info = valid_info

        indexing_time = round(time.time() - start_time, 3)

        self.metadata = {
            'dataset_dir': dataset_dir,
            'color_space': color_space,
            'hist_type': hist_type,
            'bins': list(bins) if hasattr(bins, '__iter__') else [bins, bins, bins],
            'feature_dim': int(self.features.shape[1]),
            'total_images': len(self.image_paths),
            'corrupted_count': len(corrupted_files),
            'indexing_time_sec': indexing_time,
            'indexed_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        # Lưu vào cache file dạng npz
        np.savez_compressed(
            cache_path,
            features=self.features,
            image_paths=np.array(self.image_paths, dtype=object),
            rel_paths=np.array(self.rel_paths, dtype=object),
            categories=np.array(self.categories, dtype=object),
            image_info_json=json.dumps(self.image_info),
            metadata_json=json.dumps(self.metadata)
        )

        return {
            'status': 'success',
            'message': f'Trích xuất và lưu chỉ mục thành công ({len(self.image_paths)} ảnh, {indexing_time}s)',
            'total_scanned': total_files,
            'total_valid': len(self.image_paths),
            'corrupted_count': len(corrupted_files),
            'feature_dim': int(self.features.shape[1]),
            'indexing_time_sec': indexing_time,
            'cache_file': cache_path,
            'corrupted_files': corrupted_files[:10], # Trả về tối đa 10 lỗi để xem
            'metadata': self.metadata
        }

    def load_cache(self, cache_path):
        """
        Nạp đặc trưng đã lưu sẵn từ file npz.
        """
        if not os.path.exists(cache_path):
            return False

        data = np.load(cache_path, allow_pickle=True)
        self.features = data['features'].astype(np.float32)
        self.image_paths = data['image_paths'].tolist()
        self.rel_paths = data['rel_paths'].tolist()
        self.categories = data['categories'].tolist()
        self.image_info = json.loads(str(data['image_info_json']))
        self.metadata = json.loads(str(data['metadata_json']))
        self.dataset_dir = self.metadata.get('dataset_dir', '')
        return True

    def search(self, query_vec, top_k=10, metric='chi_square'):
        """
        Tìm kiếm Top-K ảnh tương tự nhất với query_vec.
        """
        if self.features is None or len(self.features) == 0:
            return []

        distances, similarities = DistanceMetrics.compute_batch_distances(
            query_vec, self.features, metric=metric
        )

        # Sắp xếp tăng dần theo khoảng cách (khoảng cách nhỏ nhất = giống nhất)
        sorted_indices = np.argsort(distances)
        top_indices = sorted_indices[:top_k]

        results = []
        for rank_idx, i in enumerate(top_indices):
            results.append({
                'rank': rank_idx + 1,
                'index': int(i),
                'path': self.image_paths[i],
                'rel_path': self.rel_paths[i],
                'filename': self.image_info[i]['filename'],
                'category': self.categories[i],
                'width': self.image_info[i]['width'],
                'height': self.image_info[i]['height'],
                'size_kb': self.image_info[i]['size_kb'],
                'distance': round(float(distances[i]), 5),
                'similarity': round(float(similarities[i]), 2)
            })

        return results
