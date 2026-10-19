import os
import sys
import time
import uuid
import json
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename
import numpy as np

# Đảm bảo UTF-8 cho console Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from cbir import (
    ColorHistogramExtractor,
    DistanceMetrics,
    DatasetIndexer,
    DatasetEvaluator
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
DATASET_DEFAULT = os.path.join(BASE_DIR, 'dataset')
CACHE_FOLDER = os.path.join(BASE_DIR, 'index_cache')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CACHE_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB max upload

# Khởi tạo Indexer
indexer = DatasetIndexer(cache_dir=CACHE_FOLDER)
evaluator = DatasetEvaluator(indexer)

# Cấu hình trích xuất hiện thời
current_config = {
    'dataset_dir': DATASET_DEFAULT,
    'color_space': 'HSV',
    'hist_type': '3d',
    'bins': (8, 8, 8),
    'metric': 'chi_square',
    'top_k': 10
}

# Tự động nạp chỉ mục cho bộ dữ liệu mẫu mặc định khi khởi động nếu có
try:
    if os.path.exists(DATASET_DEFAULT):
        indexer.build_index(
            DATASET_DEFAULT,
            color_space=current_config['color_space'],
            hist_type=current_config['hist_type'],
            bins=current_config['bins'],
            force_rebuild=False
        )
except Exception as e:
    print(f"Khởi động ban đầu: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    """Lấy trạng thái hiện tại của hệ thống chỉ mục."""
    is_indexed = indexer.features is not None and len(indexer.features) > 0
    categories_count = {}
    if is_indexed:
        for c in indexer.categories:
            categories_count[c] = categories_count.get(c, 0) + 1

    return jsonify({
        'is_indexed': is_indexed,
        'total_images': len(indexer.image_paths) if is_indexed else 0,
        'feature_dim': int(indexer.features.shape[1]) if is_indexed else 0,
        'current_config': {
            'dataset_dir': current_config['dataset_dir'],
            'color_space': current_config['color_space'],
            'hist_type': current_config['hist_type'],
            'bins': list(current_config['bins']),
            'metric': current_config['metric'],
            'top_k': current_config['top_k']
        },
        'metadata': indexer.metadata if is_indexed else {},
        'categories_distribution': categories_count,
        'supported_metrics': DistanceMetrics.SUPPORTED_METRICS
    })

@app.route('/api/index', methods=['POST'])
def build_or_reload_index():
    """Nạp và đánh chỉ mục bộ dữ liệu ảnh."""
    data = request.get_json() or {}
    dataset_dir = data.get('dataset_dir', current_config['dataset_dir']).strip()
    color_space = data.get('color_space', current_config['color_space']).upper()
    hist_type = data.get('hist_type', current_config['hist_type']).lower()
    
    bin_val = data.get('bins', 8)
    try:
        bin_val = int(bin_val)
        bins = (bin_val, bin_val, bin_val)
    except Exception:
        bins = (8, 8, 8)

    force_rebuild = bool(data.get('force_rebuild', False))

    if not os.path.exists(dataset_dir):
        return jsonify({
            'status': 'error',
            'message': f'Thư mục không tồn tại: {dataset_dir}'
        }), 400

    # Cập nhật cấu hình hiện tại
    current_config['dataset_dir'] = dataset_dir
    current_config['color_space'] = color_space
    current_config['hist_type'] = hist_type
    current_config['bins'] = bins

    result = indexer.build_index(
        dataset_dir=dataset_dir,
        color_space=color_space,
        hist_type=hist_type,
        bins=bins,
        force_rebuild=force_rebuild
    )

    return jsonify(result)

@app.route('/api/search', methods=['POST'])
def search_images():
    """Thực hiện truy xuất ảnh tương tự theo Color Histogram."""
    if indexer.features is None or len(indexer.features) == 0:
        return jsonify({
            'status': 'error',
            'message': 'Chưa nạp chỉ mục bộ dữ liệu ảnh. Vui lòng nạp hoặc đánh chỉ mục dataset trước.'
        }), 400

    t_start = time.time()
    query_image_path = None
    is_uploaded = False

    # 1. Kiểm tra ảnh tải lên qua form-data
    if 'query_image' in request.files:
        file = request.files['query_image']
        if file and file.filename != '':
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in DatasetIndexer.VALID_EXTENSIONS:
                return jsonify({'status': 'error', 'message': f'Định dạng file không hỗ trợ: {ext}'}), 400
            
            unique_name = f"query_{uuid.uuid4().hex[:10]}{ext}"
            saved_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            file.save(saved_path)
            query_image_path = saved_path
            is_uploaded = True

    # 2. Hoặc nhận đường dẫn ảnh có sẵn từ bộ dữ liệu
    elif request.is_json:
        req_data = request.get_json()
        query_image_path = req_data.get('image_path')
        if not query_image_path or not os.path.exists(query_image_path):
            return jsonify({'status': 'error', 'message': 'Đường dẫn ảnh không hợp lệ.'}), 400

    if not query_image_path or not os.path.exists(query_image_path):
        return jsonify({'status': 'error', 'message': 'Không tìm thấy ảnh truy vấn.'}), 400

    # Lấy thông số tìm kiếm
    metric = request.form.get('metric', request.json.get('metric', current_config['metric']) if request.is_json else current_config['metric'])
    try:
        top_k = int(request.form.get('top_k', request.json.get('top_k', current_config['top_k']) if request.is_json else current_config['top_k']))
    except Exception:
        top_k = 10

    # Trích xuất đặc trưng ảnh truy vấn với cấu hình đồng nhất với index
    extractor = ColorHistogramExtractor(
        color_space=current_config['color_space'],
        hist_type=current_config['hist_type'],
        bins=current_config['bins'],
        normalize=True
    )

    t_extract_start = time.time()
    query_vec = extractor.extract(query_image_path)
    extract_time_ms = round((time.time() - t_extract_start) * 1000, 2)

    if query_vec is None:
        return jsonify({'status': 'error', 'message': 'Không thể trích xuất đặc trưng từ ảnh truy vấn.'}), 400

    # Thực hiện tìm kiếm khoảng cách
    t_search_start = time.time()
    results = indexer.search(query_vec, top_k=top_k, metric=metric)
    search_time_ms = round((time.time() - t_search_start) * 1000, 2)

    # Lấy thông tin bổ sung ảnh truy vấn (kích thước, màu chủ đạo, phân bố 3 kênh)
    is_valid, w, h, size_b, _ = indexer.validate_image(query_image_path)
    dominant_colors = extractor.extract_dominant_colors(query_image_path, k=5)
    distributions = extractor.get_display_distributions(query_image_path, num_bins=32)

    # Chuẩn bị URL hiển thị ảnh truy vấn
    if is_uploaded:
        query_url = f"/static/uploads/{os.path.basename(query_image_path)}"
    else:
        query_url = f"/api/image/view?path={query_image_path}"

    # Bổ sung URL hiển thị cho từng kết quả
    for r in results:
        r['image_url'] = f"/api/image/view?path={r['path']}"

    total_time_ms = round((time.time() - t_start) * 1000, 2)

    return jsonify({
        'status': 'success',
        'query_info': {
            'filename': os.path.basename(query_image_path),
            'path': query_image_path,
            'image_url': query_url,
            'width': w,
            'height': h,
            'size_kb': round(size_b / 1024, 1),
            'dominant_colors': dominant_colors,
            'distributions': distributions
        },
        'search_params': {
            'metric': metric,
            'metric_name': DistanceMetrics.SUPPORTED_METRICS.get(metric, metric),
            'top_k': top_k,
            'color_space': current_config['color_space'],
            'hist_type': current_config['hist_type'],
            'bins': list(current_config['bins']),
            'dataset_size': len(indexer.features)
        },
        'timing': {
            'extract_ms': extract_time_ms,
            'search_ms': search_time_ms,
            'total_ms': total_time_ms
        },
        'results': results
    })

@app.route('/api/image/view')
def view_image():
    """Xem ảnh trực tiếp từ đường dẫn trên máy tính an toàn."""
    path = request.args.get('path')
    if not path or not os.path.exists(path):
        return "Ảnh không tồn tại", 404

    # Bảo vệ chống directory traversal bên ngoài các vùng an toàn
    norm_path = os.path.abspath(path)
    return send_file(norm_path)

@app.route('/api/image/detail')
def get_image_detail():
    """Lấy chi tiết histogram và màu chủ đạo của một ảnh bất kỳ trong dataset để so sánh."""
    path = request.args.get('path')
    if not path or not os.path.exists(path):
        return jsonify({'status': 'error', 'message': 'Không tìm thấy ảnh'}), 404

    extractor = ColorHistogramExtractor(
        color_space=current_config['color_space'],
        hist_type=current_config['hist_type'],
        bins=current_config['bins'],
        normalize=True
    )

    dominant_colors = extractor.extract_dominant_colors(path, k=5)
    distributions = extractor.get_display_distributions(path, num_bins=32)

    return jsonify({
        'status': 'success',
        'filename': os.path.basename(path),
        'path': path,
        'image_url': f"/api/image/view?path={path}",
        'dominant_colors': dominant_colors,
        'distributions': distributions
    })

@app.route('/api/dataset/gallery')
def get_dataset_gallery():
    """Lấy danh sách ảnh trong dataset để người dùng duyệt và chọn làm ảnh truy vấn."""
    if indexer.features is None or len(indexer.image_paths) == 0:
        return jsonify({'items': [], 'categories': []})

    category_filter = request.args.get('category', 'all')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 30))

    items = []
    for idx, (path, rel, cat, info) in enumerate(zip(
        indexer.image_paths, indexer.rel_paths, indexer.categories, indexer.image_info
    )):
        if category_filter != 'all' and cat != category_filter:
            continue
        items.append({
            'index': idx,
            'filename': info['filename'],
            'path': path,
            'rel_path': rel,
            'category': cat,
            'width': info['width'],
            'height': info['height'],
            'size_kb': info['size_kb'],
            'image_url': f"/api/image/view?path={path}"
        })

    total_count = len(items)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paged_items = items[start_idx:end_idx]

    unique_categories = sorted(list(set(indexer.categories)))

    return jsonify({
        'items': paged_items,
        'total': total_count,
        'page': page,
        'per_page': per_page,
        'categories': unique_categories
    })

@app.route('/api/evaluate/benchmark', methods=['POST'])
def run_benchmark():
    """Kiểm thử tốc độ truy vấn."""
    data = request.get_json() or {}
    samples = int(data.get('num_samples', 30))
    metric = data.get('metric', current_config['metric'])
    res = evaluator.run_benchmark(num_samples=samples, metric=metric)
    return jsonify(res)

@app.route('/api/evaluate/precision', methods=['POST'])
def run_precision():
    """Đánh giá Precision@K theo danh mục."""
    data = request.get_json() or {}
    top_k = int(data.get('top_k', 5))
    metric = data.get('metric', current_config['metric'])
    res = evaluator.evaluate_precision_at_k(top_k=top_k, metric=metric)
    return jsonify(res)

@app.route('/api/evaluate/compare-metrics', methods=['POST'])
def compare_metrics():
    """So sánh kết quả của tất cả các metric cho cùng 1 ảnh."""
    data = request.get_json() or {}
    image_path = data.get('image_path')
    if not image_path or not os.path.exists(image_path):
        if indexer.image_paths:
            image_path = indexer.image_paths[0]
        else:
            return jsonify({'status': 'error', 'message': 'Chưa có ảnh để so sánh'}), 400

    extractor = ColorHistogramExtractor(
        color_space=current_config['color_space'],
        hist_type=current_config['hist_type'],
        bins=current_config['bins'],
        normalize=True
    )
    q_vec = extractor.extract(image_path)
    if q_vec is None:
        return jsonify({'status': 'error', 'message': 'Lỗi trích xuất'}), 400

    comparison = evaluator.compare_metrics(q_vec, top_k=5)
    
    # Bổ sung URL hiển thị cho từng kết quả
    for met, info in comparison.items():
        for r in info['results']:
            r['image_url'] = f"/api/image/view?path={r['path']}"

    return jsonify({
        'status': 'success',
        'query_path': image_path,
        'query_filename': os.path.basename(image_path),
        'comparison': comparison
    })

@app.route('/api/generate-sample', methods=['POST'])
def trigger_generate_samples():
    """Tạo lại dữ liệu ảnh mẫu nếu cần."""
    try:
        from generate_sample_data import generate_all_samples
        count = generate_all_samples()
        return jsonify({
            'status': 'success',
            'message': f'Đã tạo thành công {count} ảnh mẫu tại {DATASET_DEFAULT}'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    print("=" * 65)
    print(" HỆ THỐNG TRUY XUẤT ẢNH DỰA TRÊN COLOR HISTOGRAM (CBIR)")
    print(" Khởi chạy cục bộ tại: http://127.0.0.1:5000")
    print("=" * 65)
    app.run(host='127.0.0.1', port=5000, debug=False)
