/**
 * Grand CRM - Dynamic Autocomplete & Universal Search
 * 
 * Features:
 * - Dynamic search starting at 3 characters.
 * - Searches by first name, last name, phone, etc.
 * - Works efficiently with large datasets via server-side pagination/filtering.
 * - Universal search bar in navbar.
 * - Automatically transforms Django form selects with class 'dynamic-search-select'.
 */

(function() {
    'use strict';

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // --- 1. UNIVERSAL NAVBAR SEARCH ---
    function initUniversalSearch() {
        const input = document.getElementById('universalSearchInput');
        const resultsContainer = document.getElementById('universalSearchResults');
        const spinner = document.getElementById('universalSearchSpinner');

        if (!input || !resultsContainer) return;

        let activeIndex = -1;

        function closeResults() {
            resultsContainer.style.display = 'none';
            resultsContainer.innerHTML = '';
            activeIndex = -1;
        }

        const handleSearch = debounce(function() {
            const query = input.value.trim();

            if (query.length === 0) {
                closeResults();
                return;
            }

            if (query.length < 3) {
                resultsContainer.innerHTML = `
                    <div class="px-3 py-2 text-muted small">
                        <i class="bi bi-info-circle me-1"></i>Qidirish uchun kamida 3 ta harf kiriting (${query.length}/3)...
                    </div>
                `;
                resultsContainer.style.display = 'block';
                return;
            }

            if (spinner) spinner.classList.remove('d-none');

            fetch(`/api/search/universal/?q=${encodeURIComponent(query)}`)
                .then(res => res.json())
                .then(data => {
                    if (spinner) spinner.classList.add('d-none');
                    renderUniversalResults(data, query);
                })
                .catch(err => {
                    if (spinner) spinner.classList.add('d-none');
                    console.error('Universal search error:', err);
                });
        }, 250);

        function renderUniversalResults(data, query) {
            resultsContainer.innerHTML = '';
            activeIndex = -1;

            const total = (data.students?.length || 0) + (data.teachers?.length || 0);

            if (total === 0) {
                resultsContainer.innerHTML = `
                    <div class="p-3 text-center text-muted small">
                        <i class="bi bi-search me-1 d-block mb-1 fs-5"></i>
                        "${escapeHtml(query)}" bo'yicha hech narsa topilmadi
                    </div>
                `;
                resultsContainer.style.display = 'block';
                return;
            }

            let html = '';

            // Students Section
            if (data.students && data.students.length > 0) {
                html += `
                    <h6 class="dropdown-header text-uppercase text-primary fw-bold d-flex justify-content-between align-items-center" style="font-size: 0.72rem;">
                        <span><i class="bi bi-people-fill me-1"></i>O‘quvchilar</span>
                        <span class="badge bg-primary-subtle text-primary">${data.students.length}</span>
                    </h6>
                `;
                data.students.forEach(s => {
                    const groupsText = s.active_groups && s.active_groups.length > 0 
                        ? s.active_groups.join(', ') 
                        : 'Guruhsiz';
                    html += `
                        <a href="${s.url}" class="dropdown-item py-2 universal-item text-decoration-none">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <div class="fw-bold text-dark">${escapeHtml(s.full_name)}</div>
                                    <div class="text-muted small">
                                        <i class="bi bi-telephone me-1"></i>${escapeHtml(s.phone)} 
                                        <span class="ms-2"><i class="bi bi-collection me-1"></i>${escapeHtml(groupsText)}</span>
                                    </div>
                                </div>
                                <span class="badge bg-light text-secondary border small">${escapeHtml(s.status)}</span>
                            </div>
                        </a>
                    `;
                });
            }

            // Teachers Section
            if (data.teachers && data.teachers.length > 0) {
                if (data.students && data.students.length > 0) {
                    html += '<hr class="dropdown-divider my-1">';
                }
                html += `
                    <h6 class="dropdown-header text-uppercase text-success fw-bold d-flex justify-content-between align-items-center" style="font-size: 0.72rem;">
                        <span><i class="bi bi-person-badge-fill me-1"></i>O‘qituvchilar</span>
                        <span class="badge bg-success-subtle text-success">${data.teachers.length}</span>
                    </h6>
                `;
                data.teachers.forEach(t => {
                    html += `
                        <a href="${t.url}" class="dropdown-item py-2 universal-item text-decoration-none">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <div class="fw-bold text-dark">${escapeHtml(t.full_name)}</div>
                                    <div class="text-muted small">
                                        <i class="bi bi-telephone me-1"></i>${escapeHtml(t.phone)} 
                                        ${t.specialization ? `<span class="ms-2 badge bg-light text-dark border">${escapeHtml(t.specialization)}</span>` : ''}
                                    </div>
                                </div>
                                <span class="badge bg-light text-success border small">${t.groups_count} guruh</span>
                            </div>
                        </a>
                    `;
                });
            }

            resultsContainer.innerHTML = html;
            resultsContainer.style.display = 'block';
        }

        input.addEventListener('input', handleSearch);
        input.addEventListener('focus', function() {
            if (input.value.trim().length > 0) {
                handleSearch();
            }
        });

        // Keyboard navigation
        input.addEventListener('keydown', function(e) {
            const items = resultsContainer.querySelectorAll('.universal-item');
            if (items.length === 0 || resultsContainer.style.display === 'none') return;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                activeIndex = (activeIndex + 1) % items.length;
                updateActiveItem(items);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                activeIndex = (activeIndex - 1 + items.length) % items.length;
                updateActiveItem(items);
            } else if (e.key === 'Enter' && activeIndex >= 0) {
                e.preventDefault();
                items[activeIndex].click();
            } else if (e.key === 'Escape') {
                closeResults();
            }
        });

        function updateActiveItem(items) {
            items.forEach((item, idx) => {
                if (idx === activeIndex) {
                    item.classList.add('active', 'bg-light');
                    item.scrollIntoView({ block: 'nearest' });
                } else {
                    item.classList.remove('active', 'bg-light');
                }
            });
        }

        // Close on click outside
        document.addEventListener('click', function(e) {
            if (!input.contains(e.target) && !resultsContainer.contains(e.target)) {
                closeResults();
            }
        });
    }

    // --- 2. DYNAMIC SEARCH SELECT FOR FORMS ---
    function initDynamicSearchSelects() {
        const selects = document.querySelectorAll('select.dynamic-search-select');

        selects.forEach(select => {
            if (select.dataset.dynamicInitialized === 'true') return;
            select.dataset.dynamicInitialized = 'true';

            const searchUrl = select.dataset.searchUrl;
            if (!searchUrl) return;

            const placeholder = select.dataset.placeholder || "Qidirish uchun kamida 3 ta harf kiriting...";
            const minChars = parseInt(select.dataset.minChars, 10) || 3;

            // Hide raw select
            select.style.display = 'none';

            // Create container
            const container = document.createElement('div');
            container.className = 'dynamic-search-container';
            select.parentNode.insertBefore(container, select.nextSibling);

            function getCurrentSelected() {
                const opt = select.selectedOptions[0];
                if (opt && opt.value) {
                    return { id: opt.value, text: opt.text };
                }
                return null;
            }

            function render() {
                container.innerHTML = '';
                const current = getCurrentSelected();

                if (current) {
                    // Show Selected Card
                    const card = document.createElement('div');
                    card.className = 'selected-item-card p-2 px-3 border rounded-3 bg-white shadow-sm d-flex justify-content-between align-items-center';
                    card.innerHTML = `
                        <div class="d-flex align-items-center gap-2 overflow-hidden me-2">
                            <span class="badge bg-primary-subtle text-primary border border-primary-subtle rounded-circle p-2">
                                <i class="bi bi-person-check-fill fs-6"></i>
                            </span>
                            <div class="overflow-hidden">
                                <div class="fw-bold text-dark text-truncate">${escapeHtml(current.text)}</div>
                                <div class="text-muted small" style="font-size: 0.75rem;">Tanlangan yozuv</div>
                            </div>
                        </div>
                        <button type="button" class="btn btn-sm btn-outline-secondary py-1 px-2 btn-change-select" title="Boshqasini tanlash">
                            <i class="bi bi-pencil me-1"></i>O'zgartirish
                        </button>
                    `;

                    card.querySelector('.btn-change-select').addEventListener('click', () => {
                        renderSearchBox(current);
                    });

                    container.appendChild(card);
                } else {
                    renderSearchBox(null);
                }
            }

            function renderSearchBox(prevSelected) {
                container.innerHTML = `
                    <div class="dynamic-search-box position-relative">
                        <div class="input-group">
                            <span class="input-group-text bg-white border-end-0 text-muted"><i class="bi bi-search"></i></span>
                            <input type="text" class="form-control border-start-0 dynamic-input" placeholder="${placeholder}" autocomplete="off">
                            <span class="input-group-text bg-white border-start-0 d-none dynamic-spinner">
                                <span class="spinner-border spinner-border-sm text-primary" role="status"></span>
                            </span>
                            ${prevSelected ? `
                                <button type="button" class="btn btn-outline-secondary btn-cancel-search" title="Bekor qilish">
                                    <i class="bi bi-x-lg"></i>
                                </button>
                            ` : ''}
                        </div>
                        <div class="dropdown-menu w-100 shadow border-0 mt-1 py-1 dynamic-dropdown" style="display: none; max-height: 280px; overflow-y: auto; z-index: 1050;">
                            <div class="results-container"></div>
                        </div>
                        <div class="form-text text-muted small mt-1">
                            <i class="bi bi-keyboard me-1"></i>Ism yoki familiya bo'yicha qidiring (kamida ${minChars} ta harf).
                        </div>
                    </div>
                `;

                const box = container.querySelector('.dynamic-search-box');
                const input = box.querySelector('.dynamic-input');
                const dropdown = box.querySelector('.dynamic-dropdown');
                const resultsDiv = box.querySelector('.results-container');
                const spinner = box.querySelector('.dynamic-spinner');
                const cancelBtn = box.querySelector('.btn-cancel-search');

                if (cancelBtn) {
                    cancelBtn.addEventListener('click', () => {
                        render();
                    });
                }

                input.focus();

                let activeItemIndex = -1;

                function closeDropdown() {
                    dropdown.style.display = 'none';
                    resultsDiv.innerHTML = '';
                    activeItemIndex = -1;
                }

                const doSearch = debounce(function() {
                    const query = input.value.trim();

                    if (query.length === 0) {
                        closeDropdown();
                        return;
                    }

                    if (query.length < minChars) {
                        resultsDiv.innerHTML = `
                            <div class="px-3 py-2 text-muted small">
                                <i class="bi bi-info-circle me-1"></i>Yana ${minChars - query.length} ta harf kiriting (kamida ${minChars} ta)...
                            </div>
                        `;
                        dropdown.style.display = 'block';
                        return;
                    }

                    spinner.classList.remove('d-none');

                    fetch(`${searchUrl}?q=${encodeURIComponent(query)}`)
                        .then(res => res.json())
                        .then(data => {
                            spinner.classList.add('d-none');
                            activeItemIndex = -1;

                            if (!data.results || data.results.length === 0) {
                                resultsDiv.innerHTML = `
                                    <div class="p-3 text-center text-muted small">
                                        <i class="bi bi-search me-1 d-block mb-1 fs-5"></i>
                                        "${escapeHtml(query)}" bo'yicha hech narsa topilmadi
                                    </div>
                                `;
                                dropdown.style.display = 'block';
                                return;
                            }

                            let html = '';
                            data.results.forEach(item => {
                                html += `
                                    <button type="button" class="dropdown-item py-2 search-result-item d-flex justify-content-between align-items-center" data-id="${item.id}" data-text="${escapeHtml(item.text)}">
                                        <div>
                                            <div class="fw-bold text-dark">${escapeHtml(item.full_name || item.text)}</div>
                                            <div class="text-muted small">${escapeHtml(item.phone || item.specialization || item.group_name || '')}</div>
                                        </div>
                                        ${item.status ? `<span class="badge bg-light text-secondary border small">${escapeHtml(item.status)}</span>` : ''}
                                    </button>
                                `;
                            });

                            resultsDiv.innerHTML = html;
                            dropdown.style.display = 'block';

                            // Click item
                            resultsDiv.querySelectorAll('.search-result-item').forEach(btn => {
                                btn.addEventListener('click', function() {
                                    const itemId = this.dataset.id;
                                    const itemText = this.dataset.text;
                                    selectItem(itemId, itemText);
                                });
                            });
                        })
                        .catch(err => {
                            spinner.classList.add('d-none');
                            console.error('Search error:', err);
                        });
                }, 250);

                function selectItem(id, text) {
                    // Check if option exists in select
                    let option = select.querySelector(`option[value="${id}"]`);
                    if (!option) {
                        option = new Option(text, id, true, true);
                        select.add(option);
                    }
                    select.value = id;
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                    render();
                }

                input.addEventListener('input', doSearch);

                input.addEventListener('keydown', function(e) {
                    const items = resultsDiv.querySelectorAll('.search-result-item');
                    if (items.length === 0 || dropdown.style.display === 'none') return;

                    if (e.key === 'ArrowDown') {
                        e.preventDefault();
                        activeItemIndex = (activeItemIndex + 1) % items.length;
                        updateItems(items);
                    } else if (e.key === 'ArrowUp') {
                        e.preventDefault();
                        activeItemIndex = (activeItemIndex - 1 + items.length) % items.length;
                        updateItems(items);
                    } else if (e.key === 'Enter' && activeItemIndex >= 0) {
                        e.preventDefault();
                        items[activeItemIndex].click();
                    } else if (e.key === 'Escape') {
                        closeDropdown();
                    }
                });

                function updateItems(items) {
                    items.forEach((item, idx) => {
                        if (idx === activeItemIndex) {
                            item.classList.add('active', 'bg-primary', 'text-white');
                            item.scrollIntoView({ block: 'nearest' });
                        } else {
                            item.classList.remove('active', 'bg-primary', 'text-white');
                        }
                    });
                }

                // Close on click outside
                const clickOutsideHandler = function(e) {
                    if (!box.contains(e.target)) {
                        closeDropdown();
                    }
                };
                document.addEventListener('click', clickOutsideHandler);
            }

            render();
        });
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        initUniversalSearch();
        initDynamicSearchSelects();
    });

    // Also support HTMX / dynamic DOM updates
    document.addEventListener('htmx:afterSwap', function() {
        initDynamicSearchSelects();
    });

})();
