/**
 * CBIR Color Histogram Web App - Frontend Controller
 */

// State variables
let currentQueryFile = null;
let currentQueryPath = null;
let currentQueryData = null;
let currentCandidateData = null;
let activeModalChannel = 0;

// Chart instances
let queryHistChartInstance = null;
let modalCompareChartInstance = null;

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', () => {
    initApp();
    setupDropzone();
    setupFileInput();
});

function switchTab(tabId) {
    const tabEl = document.getElementById(`tab-${tabId}-btn`);
    if (tabEl) {
        const tab = new bootstrap.Tab(tabEl);
        tab.show();
    }
}

/**
 * 1. Khởi tạo ứng dụng và nạp trạng thái hiện tại
 */
async function initApp() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        updateStatusUI(data);
        if (data.is_indexed) {
            loadGallery(1);
        }
    } catch (err) {
        console.error('Lỗi nạp trạng thái:', err);
    }
}

function updateStatusUI(data) {
    const navBadge = document.getElementById('nav-dataset-badge');
    const infoDatasetSize = document.getElementById('info-dataset-size');
    const infoColorspace = document.getElementById('info-colorspace');
    const infoBins = document.getElementById('info-bins');

    if (data.is_indexed) {
        navBadge.className = 'badge bg-success me-3 py-2 px-3';
        navBadge.innerHTML = `<i class="fa-solid fa-check-circle me-1"></i> Đã sẵn sàng (${data.total_images} ảnh)`;
        infoDatasetSize.innerText = `${data.total_images} ảnh`;
        
        // Cập nhật tab Dataset stats
        document.getElementById('stat-valid-count').innerText = `${data.total_images} ảnh`;
        document.getElementById('stat-dim').innerText = `${data.feature_dim} chiều`;
        document.getElementById('stat-colorspace').innerText = data.current_config.color_space;
        document.getElementById('stat-cache-status').className = 'badge bg-success';
        document.getElementById('stat-cache-status').innerText = 'Đã lưu đệm (Cached)';
        
        if (data.metadata && data.metadata.indexing_time_sec) {
            document.getElementById('stat-indexing-time').innerText = `${data.metadata.indexing_time_sec} s`;
        }
        if (data.metadata && data.metadata.corrupted_count !== undefined) {
            document.getElementById('stat-corrupt-count').innerText = `${data.metadata.corrupted_count} ảnh`;
        }
    } else {
        navBadge.className = 'badge bg-warning text-dark me-3 py-2 px-3';
        navBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation me-1"></i> Chưa có chỉ mục`;
        infoDatasetSize.innerText = '0 ảnh (Cần đánh chỉ mục)';
        document.getElementById('stat-cache-status').className = 'badge bg-warning text-dark';
        document.getElementById('stat-cache-status').innerText = 'Chưa tạo';
    }

    if (data.current_config) {
        infoColorspace.innerText = data.current_config.color_space;
        const binsStr = data.current_config.bins.join('x');
        infoBins.innerText = `${binsStr} (${data.feature_dim || ''} chiều)`;
        
        // Đồng bộ form Dataset
        document.getElementById('dataset-dir-input').value = data.current_config.dataset_dir || 'dataset';
        document.getElementById('config-colorspace').value = data.current_config.color_space || 'HSV';
        document.getElementById('config-histtype').value = data.current_config.hist_type || '3d';
        document.getElementById('config-bins').value = data.current_config.bins[0] || 8;
        document.getElementById('search-metric').value = data.current_config.metric || 'chi_square';
    }
}

/**
 * 2. Xử lý Drag & Drop và File Selector
 */
function setupDropzone() {
    const dropzone = document.getElementById('drop-zone');

    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleSelectedFile(files[0]);
        }
    });
}

function setupFileInput() {
    const input = document.getElementById('query-file-input');
    input.addEventListener('change', (e) => {
        if (input.files.length > 0) {
            handleSelectedFile(input.files[0]);
        }
    });
}

function handleSelectedFile(file) {
    currentQueryFile = file;
    currentQueryPath = null;

    const reader = new FileReader();
    reader.onload = (e) => {
        const dataUrl = e.target.result;
        showQueryPreview({
            filename: file.name,
            size_kb: (file.size / 1024).toFixed(1),
            image_url: dataUrl
        });
    };
    reader.readAsDataURL(file);

    document.getElementById('btn-search-exec').disabled = false;
}

function showQueryPreview(info) {
    const box = document.getElementById('query-preview-box');
    box.classList.remove('d-none');

    document.getElementById('query-preview-img').src = info.image_url;
    document.getElementById('query-filename').innerText = info.filename;
    document.getElementById('query-filename').title = info.filename;
    document.getElementById('query-dims').innerText = info.width ? `${info.width} x ${info.height} px` : 'Đang xử lý';
    document.getElementById('query-size').innerText = `${info.size_kb} KB`;

    // Reset swatches và chart nếu là file mới chọn
    if (!info.dominant_colors) {
        document.getElementById('query-swatches').innerHTML = '<span class="text-muted x-small">Sẽ hiển thị sau khi tìm kiếm</span>';
    } else {
        renderSwatches('query-swatches', info.dominant_colors);
    }
}

function renderSwatches(containerId, colors) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';
    if (!colors || colors.length === 0) return;

    colors.forEach(c => {
        const swatch = document.createElement('span');
        swatch.className = 'color-swatch';
        swatch.style.backgroundColor = c.hex;
        swatch.title = `${c.hex} (${c.percent}%)`;
        container.appendChild(swatch);
    });
}

/**
 * 3. Thực hiện Tìm kiếm (Execute Search)
 */
async function executeSearch() {
    const btn = document.getElementById('btn-search-exec');
    const metric = document.getElementById('search-metric').value;
    const topK = document.getElementById('search-top-k').value;

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2"></i>Đang truy xuất...';

    const resultsContainer = document.getElementById('results-container');
    resultsContainer.innerHTML = `
        <div class="col-12 py-5 text-center">
            <div class="spinner-border text-primary mb-2" role="status"></div>
            <p class="text-secondary small">Đang trích xuất histogram và so sánh khoảng cách...</p>
        </div>
    `;

    try {
        let response;
        if (currentQueryFile) {
            // Upload file qua FormData
            const formData = new FormData();
            formData.append('query_image', currentQueryFile);
            formData.append('metric', metric);
            formData.append('top_k', topK);

            response = await fetch('/api/search', {
                method: 'POST',
                body: formData
            });
        } else if (currentQueryPath) {
            // Dùng ảnh từ dataset qua JSON
            response = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_path: currentQueryPath,
                    metric: metric,
                    top_k: topK
                })
            });
        } else {
            alert('Vui lòng chọn ảnh truy vấn trước!');
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-magnifying-glass me-2"></i>Tìm Kiếm Ảnh Tương Tự';
            return;
        }

        const data = await response.json();
        if (data.status === 'success') {
            currentQueryData = data.query_info;
            renderSearchResults(data);
        } else {
            resultsContainer.innerHTML = `
                <div class="col-12 alert alert-danger">
                    <i class="fa-solid fa-circle-exclamation me-2"></i>${data.message}
                </div>
            `;
        }
    } catch (err) {
        console.error('Search error:', err);
        resultsContainer.innerHTML = `
            <div class="col-12 alert alert-danger">
                Lỗi kết nối tới máy chủ tìm kiếm.
            </div>
        `;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-magnifying-glass me-2"></i>Tìm Kiếm Ảnh Tương Tự';
    }
}

/**
 * 4. Hiển thị Kết quả tìm kiếm
 */
function renderSearchResults(data) {
    const resultsContainer = document.getElementById('results-container');
    const timingBadge = document.getElementById('results-timing');
    const summarySpan = document.getElementById('results-summary');

    timingBadge.innerHTML = `<i class="fa-regular fa-clock me-1"></i> Trích xuất: ${data.timing.extract_ms}ms | Tìm: ${data.timing.search_ms}ms (Tổng: ${data.timing.total_ms}ms)`;
    summarySpan.innerHTML = `Tìm thấy <strong>${data.results.length}</strong> ảnh phù hợp nhất (Độ đo: <em>${data.search_params.metric_name}</em>)`;

    // Cập nhật lại thông tin ảnh truy vấn đầy đủ
    showQueryPreview(data.query_info);
    renderSwatches('query-swatches', data.query_info.dominant_colors);
    renderQueryHistChart(data.query_info.distributions);

    if (data.results.length === 0) {
        resultsContainer.innerHTML = '<div class="col-12 text-center text-muted py-4">Không tìm thấy ảnh nào.</div>';
        return;
    }

    resultsContainer.innerHTML = '';
    data.results.forEach(item => {
        let rankClass = 'rank-other';
        if (item.rank === 1) rankClass = 'rank-1';
        else if (item.rank === 2) rankClass = 'rank-2';
        else if (item.rank === 3) rankClass = 'rank-3';

        // Màu thanh tương đồng
        let barColor = 'bg-success';
        if (item.similarity < 50) barColor = 'bg-danger';
        else if (item.similarity < 75) barColor = 'bg-warning text-dark';

        const col = document.createElement('div');
        col.className = 'col-sm-6 col-md-4 col-xl-3';
        col.innerHTML = `
            <div class="card result-card shadow-sm border h-100">
                <div class="result-img-wrapper">
                    <img src="${item.image_url}" class="result-img" alt="${item.filename}" loading="lazy">
                    <span class="rank-badge ${rankClass}">#${item.rank}</span>
                    <span class="category-badge">${item.category}</span>
                </div>
                <div class="card-body p-2 d-flex flex-column justify-content-between">
                    <div>
                        <div class="fw-bold small text-truncate" title="${item.filename}">${item.filename}</div>
                        <div class="d-flex justify-content-between text-muted x-small mb-1">
                            <span>${item.width}x${item.height}</span>
                            <span>${item.size_kb} KB</span>
                        </div>
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="x-small text-secondary">Tương đồng:</span>
                            <span class="fw-bold small text-primary">${item.similarity}%</span>
                        </div>
                        <div class="progress mb-2" style="height: 6px;">
                            <div class="progress-bar ${barColor}" role="progressbar" style="width: ${item.similarity}%;"></div>
                        </div>
                        <div class="d-flex justify-content-between text-muted x-small mb-2">
                            <span>Khoảng cách:</span>
                            <code class="text-dark">${item.distance}</code>
                        </div>
                    </div>
                    <div class="d-flex gap-1">
                        <button class="btn btn-xs btn-outline-primary w-50 py-1 x-small" onclick="openCompareModal('${encodeURIComponent(item.path)}', ${item.similarity}, ${item.distance})">
                            <i class="fa-solid fa-code-compare me-1"></i> So sánh
                        </button>
                        <button class="btn btn-xs btn-outline-secondary w-50 py-1 x-small" onclick="useAsQueryFromDataset('${encodeURIComponent(item.path)}')">
                            <i class="fa-solid fa-arrow-rotate-left me-1"></i> Lặp lại
                        </button>
                    </div>
                </div>
            </div>
        `;
        resultsContainer.appendChild(col);
    });
}

/**
 * 5. Vẽ biểu đồ Histogram của ảnh truy vấn (Chart.js)
 */
function renderQueryHistChart(distData) {
    if (!distData) return;
    const ctx = document.getElementById('queryHistChart');
    if (!ctx) return;

    if (queryHistChartInstance) {
        queryHistChartInstance.destroy();
    }

    const datasets = [
        {
            label: distData.channel_names[0],
            data: distData.channels[0],
            borderColor: 'rgba(239, 68, 68, 0.9)',
            backgroundColor: 'rgba(239, 68, 68, 0.2)',
            borderWidth: 1.5,
            fill: true,
            tension: 0.3
        },
        {
            label: distData.channel_names[1],
            data: distData.channels[1],
            borderColor: 'rgba(34, 197, 94, 0.9)',
            backgroundColor: 'rgba(34, 197, 94, 0.2)',
            borderWidth: 1.5,
            fill: true,
            tension: 0.3
        },
        {
            label: distData.channel_names[2],
            data: distData.channels[2],
            borderColor: 'rgba(59, 130, 246, 0.9)',
            backgroundColor: 'rgba(59, 130, 246, 0.2)',
            borderWidth: 1.5,
            fill: true,
            tension: 0.3
        }
    ];

    queryHistChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: distData.bin_labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', labels: { boxWidth: 12, font: { size: 10 } } }
            },
            scales: {
                x: { display: false },
                y: { display: true, ticks: { font: { size: 9 } } }
            }
        }
    });
}

/**
 * 6. Modal So Sánh Chi Tiết (Side-by-side & Overlapping Histograms)
 */
async function openCompareModal(encodedPath, similarity, distance) {
    const imagePath = decodeURIComponent(encodedPath);
    if (!currentQueryData) {
        alert('Chưa có thông tin ảnh truy vấn.');
        return;
    }

    try {
        const res = await fetch(`/api/image/detail?path=${encodeURIComponent(imagePath)}`);
        const candidateData = await res.json();
        if (candidateData.status !== 'success') {
            alert('Không tải được thông tin ảnh đối chiếu.');
            return;
        }

        currentCandidateData = candidateData;

        // Cột Query
        document.getElementById('modal-query-img').src = currentQueryData.image_url;
        document.getElementById('modal-query-name').innerText = currentQueryData.filename;
        document.getElementById('modal-query-meta').innerText = `${currentQueryData.width}x${currentQueryData.height} px (${currentQueryData.size_kb} KB)`;
        renderSwatches('modal-query-swatches', currentQueryData.dominant_colors);

        // Cột Candidate
        document.getElementById('modal-match-img').src = candidateData.image_url;
        document.getElementById('modal-match-name').innerText = candidateData.filename;
        document.getElementById('modal-match-sim').innerText = `${similarity}% Tương đồng`;
        document.getElementById('modal-match-dist').innerText = `Khoảng cách: ${distance}`;
        renderSwatches('modal-match-swatches', candidateData.dominant_colors);

        // Cập nhật nhãn kênh
        const chNames = currentQueryData.distributions.channel_names;
        document.getElementById('lblCh0').innerText = chNames[0];
        document.getElementById('lblCh1').innerText = chNames[1];
        document.getElementById('lblCh2').innerText = chNames[2];

        // Nút dùng làm query mới
        document.getElementById('btn-modal-use-as-query').onclick = () => {
            const modalEl = document.getElementById('compareModal');
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
            useAsQueryFromDataset(encodeURIComponent(imagePath));
        };

        // Vẽ biểu đồ so sánh kênh đầu tiên
        activeModalChannel = 0;
        document.getElementById('btnCh0').checked = true;
        renderModalCompareChart();

        // Mở Modal
        const modal = new bootstrap.Modal(document.getElementById('compareModal'));
        modal.show();

    } catch (err) {
        console.error('Lỗi nạp so sánh:', err);
    }
}

function switchModalChannel(channelIdx) {
    activeModalChannel = channelIdx;
    renderModalCompareChart();
}

function renderModalCompareChart() {
    if (!currentQueryData || !currentCandidateData) return;
    const ctx = document.getElementById('modalCompareChart');
    if (!ctx) return;

    if (modalCompareChartInstance) {
        modalCompareChartInstance.destroy();
    }

    const qDist = currentQueryData.distributions;
    const cDist = currentCandidateData.distributions;
    const chName = qDist.channel_names[activeModalChannel];

    const datasets = [
        {
            label: `Query: ${chName}`,
            data: qDist.channels[activeModalChannel],
            borderColor: '#2563eb',
            backgroundColor: 'rgba(37, 99, 235, 0.25)',
            borderWidth: 2,
            fill: true,
            tension: 0.3
        },
        {
            label: `Candidate: ${chName}`,
            data: cDist.channels[activeModalChannel],
            borderColor: '#10b981',
            backgroundColor: 'rgba(16, 185, 129, 0.25)',
            borderWidth: 2,
            fill: true,
            tension: 0.3
        }
    ];

    modalCompareChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: qDist.bin_labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', labels: { boxWidth: 14 } },
                tooltip: { mode: 'index', intersect: false }
            },
            scales: {
                x: { title: { display: true, text: `Thang giá trị kênh (${qDist.color_space})` } },
                y: { title: { display: true, text: 'Phần trăm phân bố (%)' }, beginAtZero: true }
            }
        }
    });
}

/**
 * 7. Chọn ảnh từ Dataset làm ảnh truy vấn
 */
function useAsQueryFromDataset(encodedPath) {
    const imagePath = decodeURIComponent(encodedPath);
    currentQueryFile = null;
    currentQueryPath = imagePath;

    showQueryPreview({
        filename: imagePath.split(/[\\/]/).pop(),
        size_kb: 'Dataset',
        image_url: `/api/image/view?path=${encodeURIComponent(imagePath)}`
    });

    document.getElementById('btn-search-exec').disabled = false;
    switchTab('search');
    executeSearch();
}

async function openDatasetPickerModal() {
    try {
        const res = await fetch('/api/dataset/gallery?per_page=60');
        const data = await res.json();
        const grid = document.getElementById('picker-grid');
        grid.innerHTML = '';

        if (!data.items || data.items.length === 0) {
            grid.innerHTML = '<div class="col-12 text-center text-muted py-4">Chưa có ảnh trong dataset. Hãy nạp dataset trước.</div>';
        } else {
            data.items.forEach(item => {
                const col = document.createElement('div');
                col.className = 'col-3 col-sm-2 text-center';
                col.innerHTML = `
                    <div class="gallery-item-card border p-1" onclick="selectPickerImage('${encodeURIComponent(item.path)}')">
                        <img src="${item.image_url}" class="img-fluid rounded gallery-item-img" alt="${item.filename}">
                        <div class="x-small text-truncate mt-1">${item.filename}</div>
                    </div>
                `;
                grid.appendChild(col);
            });
        }

        const modal = new bootstrap.Modal(document.getElementById('datasetPickerModal'));
        modal.show();
    } catch (err) {
        console.error('Picker error:', err);
    }
}

function selectPickerImage(encodedPath) {
    const modalEl = document.getElementById('datasetPickerModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
    useAsQueryFromDataset(encodedPath);
}

/**
 * 8. Quản lý Dataset & Đánh Chỉ Mục (Tab 2)
 */
async function startDatasetIndexing() {
    const btn = document.getElementById('btn-start-index');
    const datasetDir = document.getElementById('dataset-dir-input').value;
    const colorSpace = document.getElementById('config-colorspace').value;
    const histType = document.getElementById('config-histtype').value;
    const bins = parseInt(document.getElementById('config-bins').value, 10);
    const forceRebuild = document.getElementById('force-rebuild-check').checked;

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2"></i>Đang quét và trích xuất chỉ mục...';

    try {
        const res = await fetch('/api/index', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dataset_dir: datasetDir,
                color_space: colorSpace,
                hist_type: histType,
                bins: bins,
                force_rebuild: forceRebuild
            })
        });

        const data = await res.json();
        if (data.status === 'success' || data.status === 'loaded_from_cache') {
            alert(`✅ ${data.message}`);
            initApp();
            loadGallery(1);
        } else {
            alert(`❌ Lỗi: ${data.message}`);
        }
    } catch (err) {
        console.error('Indexing error:', err);
        alert('Lỗi gửi yêu cầu trích xuất chỉ mục.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-bolt me-2"></i>Nạp & Đánh Chỉ Mục Dữ Liệu';
    }
}

async function generateSampleDataset() {
    if (!confirm('Tạo bộ dữ liệu 50 ảnh mẫu (5 danh mục màu sắc)?')) return;
    try {
        const res = await fetch('/api/generate-sample', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
            alert(data.message);
            // Tự động index lại bộ mẫu
            document.getElementById('force-rebuild-check').checked = true;
            startDatasetIndexing();
        } else {
            alert('Lỗi tạo mẫu: ' + data.message);
        }
    } catch (err) {
        alert('Lỗi kết nối tạo ảnh mẫu.');
    }
}

async function loadGallery(page = 1) {
    const filter = document.getElementById('gallery-category-filter').value;
    const grid = document.getElementById('gallery-grid');
    grid.innerHTML = '<div class="col-12 text-center py-4"><div class="spinner-border spinner-border-sm text-secondary"></div></div>';

    try {
        const res = await fetch(`/api/dataset/gallery?category=${filter}&page=${page}&per_page=24`);
        const data = await res.json();

        // Cập nhật dropdown categories nếu chưa có
        const catSelect = document.getElementById('gallery-category-filter');
        if (catSelect.options.length <= 1 && data.categories) {
            data.categories.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c;
                opt.innerText = c;
                catSelect.appendChild(opt);
            });
        }

        grid.innerHTML = '';
        if (data.items.length === 0) {
            grid.innerHTML = '<div class="col-12 text-center text-muted py-4">Chưa có ảnh nào.</div>';
            return;
        }

        data.items.forEach(item => {
            const col = document.createElement('div');
            col.className = 'col-4 col-sm-3 col-md-2';
            col.innerHTML = `
                <div class="gallery-item-card border" onclick="useAsQueryFromDataset('${encodeURIComponent(item.path)}')">
                    <img src="${item.image_url}" class="gallery-item-img" alt="${item.filename}" loading="lazy">
                    <div class="gallery-item-overlay">
                        <div>${item.filename}</div>
                    </div>
                </div>
            `;
            grid.appendChild(col);
        });

        // Pagination
        const pagContainer = document.getElementById('gallery-pagination');
        pagContainer.innerHTML = '';
        const totalPages = Math.ceil(data.total / data.per_page);
        if (totalPages > 1) {
            for (let p = 1; p <= totalPages; p++) {
                const b = document.createElement('button');
                b.className = `btn btn-sm ${p === page ? 'btn-primary' : 'btn-outline-secondary'}`;
                b.innerText = p;
                b.onclick = () => loadGallery(p);
                pagContainer.appendChild(b);
            }
        }
    } catch (err) {
        console.error('Gallery load error:', err);
    }
}

/**
 * 9. Kiểm thử & Đánh giá (Tab 3)
 */
async function runBenchmarkTest() {
    const container = document.getElementById('benchmark-results');
    container.innerHTML = '<div class="text-center py-4"><div class="spinner-border spinner-border-sm text-primary mb-2"></div><div class="small text-muted">Đang chạy đo tốc độ...</div></div>';

    try {
        const res = await fetch('/api/evaluate/benchmark', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ num_samples: 30 })
        });
        const data = await res.json();
        if (data.status === 'success') {
            container.innerHTML = `
                <div class="row g-2 text-center">
                    <div class="col-6 col-sm-4">
                        <div class="p-2 bg-white rounded border">
                            <div class="text-muted x-small">Độ trễ trung bình</div>
                            <div class="fw-bold text-primary fs-5">${data.avg_latency_ms} ms</div>
                        </div>
                    </div>
                    <div class="col-6 col-sm-4">
                        <div class="p-2 bg-white rounded border">
                            <div class="text-muted x-small">Throughput (QPS)</div>
                            <div class="fw-bold text-success fs-5">${data.queries_per_second}</div>
                        </div>
                    </div>
                    <div class="col-6 col-sm-4">
                        <div class="p-2 bg-white rounded border">
                            <div class="text-muted x-small">Nhanh nhất / Chậm nhất</div>
                            <div class="fw-bold text-dark small">${data.min_latency_ms} / ${data.max_latency_ms} ms</div>
                        </div>
                    </div>
                    <div class="col-6 col-sm-6">
                        <div class="p-2 bg-white rounded border">
                            <div class="text-muted x-small">Độ trễ Percentile 95 (P95)</div>
                            <div class="fw-bold text-info">${data.p95_latency_ms} ms</div>
                        </div>
                    </div>
                    <div class="col-12 col-sm-6">
                        <div class="p-2 bg-white rounded border">
                            <div class="text-muted x-small">Quy mô kiểm thử</div>
                            <div class="fw-bold text-secondary small">${data.num_queries_tested} truy vấn trên ${data.dataset_size} ảnh</div>
                        </div>
                    </div>
                </div>
            `;
        } else {
            container.innerHTML = `<div class="alert alert-danger mb-0">${data.message}</div>`;
        }
    } catch (err) {
        container.innerHTML = '<div class="alert alert-danger mb-0">Lỗi đo tốc độ.</div>';
    }
}

async function runPrecisionTest() {
    const container = document.getElementById('precision-results');
    container.innerHTML = '<div class="text-center py-4"><div class="spinner-border spinner-border-sm text-success mb-2"></div><div class="small text-muted">Đang tính toán Precision@K trên từng danh mục...</div></div>';

    try {
        const res = await fetch('/api/evaluate/precision', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ top_k: 5 })
        });
        const data = await res.json();
        if (data.status === 'success') {
            let catRows = '';
            for (const [cat, info] of Object.entries(data.per_category)) {
                catRows += `
                    <tr>
                        <td><strong>${cat}</strong></td>
                        <td>${info.count_tested}</td>
                        <td>
                            <div class="d-flex align-items-center">
                                <div class="progress flex-grow-1 me-2" style="height: 6px;">
                                    <div class="progress-bar bg-success" style="width: ${info.precision_pct}%"></div>
                                </div>
                                <span class="small fw-bold">${info.precision_pct}%</span>
                            </div>
                        </td>
                    </tr>
                `;
            }

            container.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-3 p-2 bg-white rounded border">
                    <div>
                        <div class="text-muted x-small">Mean Precision@${data.top_k}</div>
                        <div class="fw-bold text-success fs-4">${data.mean_precision_pct}%</div>
                    </div>
                    <span class="badge bg-success py-2 px-3">Đánh giá trên ${data.total_evaluated} mẫu</span>
                </div>
                <div class="table-responsive">
                    <table class="table table-sm table-bordered bg-white mb-0 x-small">
                        <thead class="table-light">
                            <tr>
                                <th>Danh mục (Thư mục con)</th>
                                <th>Số mẫu test</th>
                                <th>Precision@${data.top_k}</th>
                            </tr>
                        </thead>
                        <tbody>${catRows}</tbody>
                    </table>
                </div>
            `;
        } else {
            container.innerHTML = `<div class="alert alert-warning mb-0">${data.message}</div>`;
        }
    } catch (err) {
        container.innerHTML = '<div class="alert alert-danger mb-0">Lỗi đánh giá Precision.</div>';
    }
}

async function runMetricComparison() {
    const container = document.getElementById('comparison-results');
    container.innerHTML = '<div class="text-center py-4"><div class="spinner-border spinner-border-sm text-info mb-2"></div><div class="small text-muted">Đang chạy đối chiếu 7 công thức khoảng cách...</div></div>';

    try {
        const payload = currentQueryPath ? { image_path: currentQueryPath } : {};
        const res = await fetch('/api/evaluate/compare-metrics', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === 'success') {
            let tableHTML = `
                <div class="mb-2 small text-secondary">
                    Ảnh đối chiếu: <strong>${data.query_filename}</strong>
                </div>
                <table class="table table-bordered table-hover align-middle x-small bg-white">
                    <thead class="table-light">
                        <tr>
                            <th style="width: 180px;">Công Thức / Độ Đo</th>
                            <th style="width: 80px;">Thời Gian</th>
                            <th>Top 1 (Trùng nhất)</th>
                            <th>Top 2</th>
                            <th>Top 3</th>
                            <th>Top 4</th>
                            <th>Top 5</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            for (const [mId, mInfo] of Object.entries(data.comparison)) {
                tableHTML += `
                    <tr>
                        <td><strong>${mInfo.metric_name}</strong></td>
                        <td><span class="badge bg-light text-dark border">${mInfo.latency_ms} ms</span></td>
                `;
                mInfo.results.forEach(r => {
                    tableHTML += `
                        <td class="text-center" style="width: 14%;">
                            <img src="${r.image_url}" class="rounded border mb-1" style="width: 48px; height: 48px; object-fit: cover;">
                            <div class="text-truncate fw-semibold" style="max-width: 90px;">${r.filename}</div>
                            <div class="text-muted" style="font-size: 0.65rem;">d=${r.distance} (${r.similarity}%)</div>
                        </td>
                    `;
                });
                tableHTML += `</tr>`;
            }
            tableHTML += `</tbody></table>`;
            container.innerHTML = tableHTML;
        } else {
            container.innerHTML = `<div class="alert alert-danger mb-0">${data.message}</div>`;
        }
    } catch (err) {
        container.innerHTML = '<div class="alert alert-danger mb-0">Lỗi so sánh các metric.</div>';
    }
}
