import cv2
import numpy as np
from PIL import Image
import os

class ColorHistogramExtractor:
    """
    Trích xuất đặc trưng Color Histogram cho ảnh.
    Hỗ trợ các không gian màu: RGB, HSV, Lab.
    Hỗ trợ 3D Joint Histogram và 1D Concatenated Histogram.
    """

    def __init__(self, color_space='HSV', hist_type='3d', bins=(8, 8, 8), normalize=True):
        self.color_space = color_space.upper()
        self.hist_type = hist_type.lower()
        if isinstance(bins, int):
            self.bins = (bins, bins, bins)
        else:
            self.bins = tuple(bins)
        self.normalize = normalize

    @staticmethod
    def read_image_safe(image_source):
        """
        Đọc ảnh an toàn, hỗ trợ đường dẫn Unicode trên Windows và PIL Image / numpy array.
        Trả về ảnh ở định dạng BGR (OpenCV format) hoặc None nếu lỗi.
        """
        if isinstance(image_source, np.ndarray):
            if len(image_source.shape) == 2:
                return cv2.cvtColor(image_source, cv2.COLOR_GRAY2BGR)
            elif image_source.shape[2] == 4:
                return cv2.cvtColor(image_source, cv2.COLOR_BGRA2BGR)
            return image_source

        if isinstance(image_source, Image.Image):
            rgb = np.array(image_source.convert('RGB'))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        if isinstance(image_source, str):
            if not os.path.exists(image_source):
                return None
            try:
                # Dùng np.fromfile và cv2.imdecode để tránh lỗi đường dẫn chứa tiếng Việt / Unicode trên Windows
                img_array = np.fromfile(image_source, dtype=np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if img is not None:
                    return img
            except Exception:
                pass
            
            # Dự phòng bằng Pillow
            try:
                with Image.open(image_source) as pil_img:
                    rgb = np.array(pil_img.convert('RGB'))
                    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            except Exception:
                return None

        return None

    def convert_color_space(self, bgr_image):
        """
        Chuyển đổi ảnh BGR sang không gian màu mong muốn.
        """
        if self.color_space == 'RGB':
            return cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        elif self.color_space == 'HSV':
            return cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
        elif self.color_space == 'LAB':
            return cv2.cvtColor(bgr_image, cv2.COLOR_BGR2Lab)
        else:
            # Mặc định RGB
            return cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)

    def get_channel_ranges(self):
        """
        Trả về dải giá trị của các kênh tương ứng với không gian màu.
        """
        if self.color_space == 'HSV':
            # Trong OpenCV: H trong [0, 180), S trong [0, 256), V trong [0, 256)
            return [0, 180, 0, 256, 0, 256]
        else:
            # RGB hoặc LAB trong OpenCV đều có dải 0..256
            return [0, 256, 0, 256, 0, 256]

    def extract(self, image_source):
        """
        Trích xuất histogram đặc trưng dưới dạng vector 1D float32.
        Trả về None nếu không đọc được ảnh.
        """
        bgr = self.read_image_safe(image_source)
        if bgr is None or bgr.size == 0:
            return None

        converted = self.convert_color_space(bgr)
        ranges = self.get_channel_ranges()

        if self.hist_type == '3d':
            # 3D Joint Histogram
            hist = cv2.calcHist(
                [converted],
                [0, 1, 2],
                None,
                list(self.bins),
                ranges
            )
            feature_vector = hist.flatten().astype(np.float32)
        else:
            # 1D Concatenated Histogram (từng kênh riêng biệt)
            h0 = cv2.calcHist([converted], [0], None, [self.bins[0]], [ranges[0], ranges[1]]).flatten()
            h1 = cv2.calcHist([converted], [1], None, [self.bins[1]], [ranges[2], ranges[3]]).flatten()
            h2 = cv2.calcHist([converted], [2], None, [self.bins[2]], [ranges[4], ranges[5]]).flatten()
            feature_vector = np.concatenate([h0, h1, h2]).astype(np.float32)

        if self.normalize:
            # Chuẩn hóa L1 (tổng bằng 1) biểu thị phân bố xác suất
            total = np.sum(feature_vector)
            if total > 1e-7:
                feature_vector /= total
            else:
                feature_vector = np.zeros_like(feature_vector)

        return feature_vector

    def get_display_distributions(self, image_source, num_bins=32):
        """
        Trích xuất phân bố màu 3 kênh riêng biệt để vẽ biểu đồ trực quan (Chart.js).
        Trả về dict chứa nhãn và giá trị 3 kênh.
        """
        bgr = self.read_image_safe(image_source)
        if bgr is None:
            return None

        converted = self.convert_color_space(bgr)
        ranges = self.get_channel_ranges()

        ch0 = cv2.calcHist([converted], [0], None, [num_bins], [ranges[0], ranges[1]]).flatten()
        ch1 = cv2.calcHist([converted], [1], None, [num_bins], [ranges[2], ranges[3]]).flatten()
        ch2 = cv2.calcHist([converted], [2], None, [num_bins], [ranges[4], ranges[5]]).flatten()

        # Chuẩn hóa về phần trăm hiển thị
        s0, s1, s2 = np.sum(ch0) + 1e-7, np.sum(ch1) + 1e-7, np.sum(ch2) + 1e-7
        ch0_norm = (ch0 / s0 * 100).round(2).tolist()
        ch1_norm = (ch1 / s1 * 100).round(2).tolist()
        ch2_norm = (ch2 / s2 * 100).round(2).tolist()

        if self.color_space == 'HSV':
            labels = ["Hue (Sắc độ)", "Saturation (Độ bão hòa)", "Value (Độ sáng)"]
            bin_labels = [f"{int(i * 180 / num_bins)}" for i in range(num_bins)]
        elif self.color_space == 'LAB':
            labels = ["L* (Độ sáng)", "a* (Lục - Đỏ)", "b* (Lam - Vàng)"]
            bin_labels = [f"{int(i * 256 / num_bins)}" for i in range(num_bins)]
        else: # RGB
            labels = ["Red (Đỏ)", "Green (Lục)", "Blue (Lam)"]
            bin_labels = [f"{int(i * 256 / num_bins)}" for i in range(num_bins)]

        return {
            'color_space': self.color_space,
            'channel_names': labels,
            'bin_labels': bin_labels,
            'channels': [ch0_norm, ch1_norm, ch2_norm]
        }

    @staticmethod
    def extract_dominant_colors(image_source, k=5):
        """
        Trích xuất k màu chủ đạo của ảnh bằng K-Means để hiển thị bảng mã màu (swatches).
        """
        bgr = ColorHistogramExtractor.read_image_safe(image_source)
        if bgr is None:
            return []
        
        # Thu nhỏ để xử lý k-means cực nhanh
        small = cv2.resize(bgr, (64, 64), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        pixels = rgb.reshape(-1, 3).astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        flags = cv2.KMEANS_RANDOM_CENTERS
        compactness, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3, flags)

        counts = np.bincount(labels.flatten())
        total = np.sum(counts)

        dominant_colors = []
        for i in np.argsort(-counts):
            c = centers[i].astype(int)
            hex_code = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
            percent = round(float(counts[i]) / total * 100, 1)
            dominant_colors.append({
                'hex': hex_code,
                'rgb': [int(c[0]), int(c[1]), int(c[2])],
                'percent': percent
            })

        return dominant_colors
