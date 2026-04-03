// Global cache for frequently used selectors (populated on DOMContentLoaded)
var CACHED = {
    containers: null,
    tables: null,
    tablesSortable: null,
    filterBtns: null,
    manuBtns: null,
    productCells: null,
    searchInput: null,
};

// Browser feature flag
var IS_FIREFOX = typeof InstallTrigger !== 'undefined';

    document.addEventListener("DOMContentLoaded", function() {
    // Populate caches once
    CACHED.containers = document.querySelectorAll('div.container');
    CACHED.tables = document.querySelectorAll('table');
    CACHED.tablesSortable = document.querySelectorAll('table.sortable');
    CACHED.filterBtns = document.querySelectorAll('.filter-btn');
    CACHED.manuBtns = document.querySelectorAll('.manufacturer-filter-btn');
    CACHED.productCells = document.querySelectorAll('td[data-manufacturer]');
    CACHED.searchInput = document.getElementById('searchInput');

    // Firefox first-focus jank mitigation: disable browser autofill heuristics
    // and set numeric input hints before any focus occurs.
    try {
        var bulkForm = document.querySelector('form.bulk-edit');
        if (bulkForm) {
            bulkForm.setAttribute('autocomplete', 'off');
            bulkForm.setAttribute('spellcheck', 'false');
        }
        // Disable autocomplete and spellcheck on all text/number inputs
        var allInputs = document.querySelectorAll('input[type="text"], input[type="number"]');
        allInputs.forEach(function(inp){
            inp.setAttribute('autocomplete', 'off');
            inp.setAttribute('autocapitalize', 'off');
            inp.setAttribute('autocorrect', 'off');
            inp.setAttribute('spellcheck', 'false');
        });
        // Hint numeric entry for price/discount fields without changing type
        document.querySelectorAll('.special-price-input, .discount-percent-input').forEach(function(inp){
            inp.setAttribute('inputmode', 'decimal');
        });
    } catch(e) { /* no-op */ }

    // Firefox prewarm: trigger autofill module load off the critical first input focus
    if (IS_FIREFOX) {
        let ffPrewarmed = false;
        const ffPrewarm = function() {
            if (ffPrewarmed) return; ffPrewarmed = true;
            try {
                const dummy = document.createElement('input');
                dummy.type = 'text';
                dummy.style.position = 'fixed';
                dummy.style.left = '-9999px';
                dummy.style.top = '-9999px';
                dummy.setAttribute('autocomplete', 'off');
                dummy.setAttribute('aria-hidden', 'true');
                document.body.appendChild(dummy);
                dummy.focus();
                dummy.blur();
                document.body.removeChild(dummy);
            } catch(_) {}
        };
        if ('requestIdleCallback' in window) {
            requestIdleCallback(ffPrewarm, { timeout: 300 });
        } else {
            setTimeout(ffPrewarm, 150);
        }
        const onFirstMove = function() { ffPrewarm(); document.removeEventListener('mousemove', onFirstMove, true); };
        document.addEventListener('mousemove', onFirstMove, true);
    }
    // Manufacturer filter buttons for bulk_edit.html
    (CACHED.manuBtns || document.querySelectorAll('.manufacturer-filter-btn')).forEach(button => {
        button.addEventListener('click', function() {
            const manufacturer = this.getAttribute('data-manufacturer');
            const isActive = this.classList.contains('active');
            // Remove active from all, then toggle this one if not already active
            (CACHED.manuBtns || document.querySelectorAll('.manufacturer-filter-btn')).forEach(btn => btn.classList.remove('active'));
            let showAll = false;
            if (isActive || manufacturer === 'all') {
                showAll = true;
            } else {
                this.classList.add('active');
            }
            // Only set cell visibility, do not touch container/table display
            const productCells = CACHED.productCells || document.querySelectorAll('td[data-manufacturer]');
            if (showAll) {
                productCells.forEach(cell => {
                    cell.style.visibility = '';
                });
            } else {
                productCells.forEach(cell => {
                    if (cell.getAttribute('data-manufacturer') === manufacturer) {
                        cell.style.visibility = '';
                    } else {
                        cell.style.visibility = 'hidden';
                    }
                });
            }
            // Hide rows if all product cells in the row are hidden (works for all tables)
            (CACHED.tablesSortable || document.querySelectorAll('table.sortable')).forEach(table => {
                const rows = Array.from(table.querySelectorAll('tbody tr'));
                rows.forEach(row => {
                    const productCells = Array.from(row.querySelectorAll('td[data-manufacturer]'));
                    if (productCells.length > 0) {
                        const allHidden = productCells.every(cell => cell.style.visibility === 'hidden');
                        row.style.display = allHidden ? 'none' : '';
                    }
                });
            });
            // If search bar is not empty, re-apply search filter
            var searchInput = CACHED.searchInput || document.getElementById('searchInput');
            if (searchInput && searchInput.value.trim() !== '') {
                searchInput.dispatchEvent(new Event('input'));
            }
            storeFilterState();
        });
    });
        // Manufacturer dropdown on proposed_order.html
        var manufacturerSelect = document.getElementById('manufacturer-select');
        if (manufacturerSelect) {
            manufacturerSelect.addEventListener('change', function() {
                var sel = this;
                if (sel && sel.value) {
                    window.location.href = '/order/' + encodeURIComponent(sel.value);
                }
            });
        }
    var currentPage = window.location.href;

    // Check if the page is different from the previously stored page
    var storedPage = localStorage.getItem('currentPage');
    if (storedPage !== currentPage) {
        // Clear localStorage items if the page is different
        localStorage.removeItem('scrollPosition');
        localStorage.removeItem('searchInputValue');
        // Clear all session-based UI state to avoid carrying over state across pages
        sessionStorage.removeItem('hiddenTables');
        sessionStorage.removeItem('activeManufacturer');
        sessionStorage.removeItem('bulkEditTable');
        sessionStorage.removeItem('bulkEditAttr');
        sessionStorage.removeItem('bulkEditSearch');
        sessionStorage.removeItem('bulkEditScroll');
        sessionStorage.removeItem('bulkEditFilter');
        sessionStorage.removeItem('selectedRowKey');
        sessionStorage.removeItem('activeMainFilter');
        sessionStorage.removeItem('selectedRowDomId');
        showAllTables();
    }
    else {
        // Restore the filter state from sessionStorage
        restoreFilterState();
        if (localStorage.getItem('searchInputValue') !== null) {
            var searchInput = document.getElementById('searchInput');
            searchInput.value = localStorage.getItem('searchInputValue');
            searchTable(); // Make sure search is applied before further actions
        }
        restoreRowHighlight();
    }

    // Update the stored page to the current page
    localStorage.setItem('currentPage', currentPage);

    if (sessionStorage.getItem("toggled") === null) {
        sessionStorage.setItem("toggled", "false");
    }
    if (document.title.indexOf("Grow Kit") !== -1 && sessionStorage.getItem("toggled") === "true") {
        toggleEmptyRows(true);
    }

    var theme = sessionStorage.getItem('theme');
    if (theme === 'light') {
        document.body.classList.add('light-mode');
    } else {
        document.body.classList.remove('light-mode');
    }

    document.getElementById('toggle-theme').addEventListener('click', function () {
        var isLightMode = document.body.classList.contains('light-mode');
        if (isLightMode) {
            document.body.classList.remove('light-mode');
            sessionStorage.setItem('theme', 'dark');
        } else {
            document.body.classList.add('light-mode');
            sessionStorage.setItem('theme', 'light');
        }
    });

    // Removed thousands of per-input focus listeners; handled via a single focusin delegate below

    // Highlight row on input focus and save row key for restoration
    // Defer the very first focus work by one frame on Firefox to avoid long jank,
    // and skip select/highlight entirely on the first focus to minimize style churn.
    var firstFocusDeferred = false;
    var firstFocusHandled = false;
    document.addEventListener('focusin', function(e) {
        if (!(e.target && (e.target.matches('input[type="number"]') || e.target.matches('input[type="text"]')))) return;
        var run = function(){
            if (IS_FIREFOX && !firstFocusHandled) {
                // Mark handled and intentionally do nothing on the very first focus
                // (no select, no highlight) to avoid extra layout/style work.
                firstFocusHandled = true;
                return;
            }
            try { e.target.select(); } catch(_) {}
            var tr = e.target.closest('tr');
            if (tr) {
                document.querySelectorAll('tr.highlight').forEach(r => r.classList.remove('highlight'));
                tr.classList.add('highlight');
                var key = tr.getAttribute('data-key');
                if (!key) {
                    var firstCell = tr.querySelector('td');
                    if (firstCell) key = firstCell.textContent.trim();
                }
                if (key) sessionStorage.setItem('selectedRowKey', String(key));
            }
        };
        if (IS_FIREFOX && !firstFocusDeferred) {
            firstFocusDeferred = true;
            return requestAnimationFrame(run);
        }
        run();
    });

    var toggleButton = document.getElementById('toggle-button');
    if (toggleButton) {
        toggleButton.addEventListener('click', handleToggleClick);
    }

    // Style the top-level Edit toggle button like other toggles
    (function initEditToggleButton(){
        try {
            var mainEditBtns = document.querySelectorAll('button[onclick^="replaceButtons("]');
            mainEditBtns.forEach(function(btn){
                btn.classList.add('edit-toggle-btn');
                btn.setAttribute('aria-pressed', 'false');
            });
        } catch(_) {}
    })();

    // Update on window resize
    window.addEventListener('resize', updateTableHeaderTop);

    // Store scroll position and filter state before form submission
    const stockForms = document.querySelectorAll('form.stock_input');
    stockForms.forEach(function(form) {
        form.addEventListener('submit', function() {
            localStorage.setItem('scrollPosition', window.scrollY);
            storeFilterState(); // Save the current filter state
            const tr = form.closest('tr'); // save highlighted row
            const key =
                form.querySelector('input[name="item_id"]')?.value || // if present
                tr?.getAttribute('data-key');

            if (key) {
                sessionStorage.setItem('selectedRowKey', String(key));
            }
        });
        });

    // --- Bulk Edit: Store state before update all ---
    var updateAllBtn = document.querySelector('button[onclick="updateAllBulkEdit()"]');
    if (updateAllBtn) {
        updateAllBtn.addEventListener('click', function() {
            storeBulkEditState();
        });
    }

    // --- Bulk Edit: Store state before dropdown/view change ---
    var updateSelectionBtn = document.getElementById("updateSelection");
    if (updateSelectionBtn) {
        updateSelectionBtn.addEventListener('click', function() {
            storeBulkEditState();
        });
    }

    // Restore scroll position
    if (localStorage.getItem('scrollPosition') !== null) {
        window.scrollTo(0, localStorage.getItem('scrollPosition'));
        // localStorage.removeItem('scrollPosition'); // Optional: remove after use if desired
    }

    // Restore filter state
    // restoreFilterState();

    // Restore search input value and perform search
    if (localStorage.getItem('searchInputValue') !== null) {
        var searchInput = document.getElementById('searchInput');
        searchInput.value = localStorage.getItem('searchInputValue');
        searchTable();
        // localStorage.removeItem('searchInputValue'); // Optional: remove after use if desired
    }

    // Add event listener to search input
    var searchInput = CACHED.searchInput || document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            localStorage.setItem('searchInputValue', searchInput.value);
            // Only show/hide rows, do not touch cell visibility or container display
            var filter = searchInput.value.toUpperCase().trim();
            var tables = CACHED.tables || document.querySelectorAll("table");
            for (var t = 0; t < tables.length; t++) {
                var table = tables[t];
                var hasVisibleRow = false;
                var rows = table.rows;
                for (var r = 1; r < rows.length; r++) {
                    var row = rows[r];
                    var rowHasMatch = false;
                    var cells = row.cells;
                    for (var c = 0; c < cells.length; c++) {
                        if (cells[c].textContent.toUpperCase().indexOf(filter) > -1) {
                            rowHasMatch = true;
                            break;
                        }
                    }
                    // Only show row if it matches and is not hidden by manufacturer filter
                    var manuHidden = rowIsManufacturerHidden(row);
                    if (!rowHasMatch || manuHidden) {
                        row.style.display = 'none';
                    } else {
                        row.style.display = '';
                        hasVisibleRow = true;
                    }
                }
                table.style.display = hasVisibleRow ? "" : "none";
            }
            storeFilterState();
        });

        // If on the log page, also wire client-side filtering of pre.log-output
        var logPre = document.querySelector('pre.log-output');
        if (logPre) {
            // Cache original highlighted HTML lines once
            if (!logPre.__origLines) {
                logPre.__origLines = (logPre.innerHTML || '').split(/\n/);
            }
            var applyLogFilter = function() {
                var q = (searchInput.value || '').trim().toLowerCase();
                if (!q) {
                    logPre.innerHTML = logPre.__origLines.join('\n');
                    return;
                }
                var filtered = [];
                for (var i = 0; i < logPre.__origLines.length; i++) {
                    var line = logPre.__origLines[i];
                    if (line.toLowerCase().indexOf(q) !== -1) filtered.push(line);
                }
                logPre.innerHTML = filtered.join('\n');
            };
            // Expose a clear hook used by the Clear button
            window.__resetLogFilter = function() {
                if (!logPre || !logPre.__origLines) return;
                logPre.innerHTML = logPre.__origLines.join('\n');
            };
            searchInput.addEventListener('input', applyLogFilter);
        }
    }

    // Delegated row click handler to avoid thousands of listeners
    document.addEventListener('click', function(evt) {
        const row = evt.target && evt.target.closest('tr');
        if (!row || !row.closest('table')) return;
        // remove previous highlights
        document.querySelectorAll('tr.highlight').forEach(r => r.classList.remove('highlight'));
        // add highlight to selected
        row.classList.add('highlight');

        // persist selected row key on any row click (including clicks on inputs)
        let key = row.getAttribute('data-key');
        if (!key) {
            const idInput = row.querySelector('input[name="item_id"]');
            if (idInput && idInput.value) {
                key = String(idInput.value);
            } else {
                const firstCell = row.querySelector('td');
                if (firstCell) key = firstCell.textContent.trim();
            }
        }
        if (key) sessionStorage.setItem('selectedRowKey', String(key));
    });

    // Add event listeners for filter buttons
    (CACHED.filterBtns || document.querySelectorAll('.filter-btn')).forEach(button => {
        button.addEventListener('click', function() {
            const filterType = this.getAttribute('data-table');
            const currentlyActive = this.classList.contains('active');
            const containers = Array.from(CACHED.containers || document.querySelectorAll('div.container'));
            const allTypes = containers.map(c => c.getAttribute('data-table'));

            // Visual toggle
            (CACHED.filterBtns || document.querySelectorAll('.filter-btn')).forEach(btn => btn.classList.remove('active'));
            if (filterType === 'all' || currentlyActive) {
                showAllTables();
                // Persist explicit state for "all"
                sessionStorage.setItem('hiddenTables', JSON.stringify([]));
                sessionStorage.setItem('activeMainFilter', 'all');
            } else {
                filterTables(filterType);
                this.classList.add('active');
                // Persist explicit state for a single-table filter
                const hiddenTables = allTypes.filter(t => t !== filterType);
                sessionStorage.setItem('hiddenTables', JSON.stringify(hiddenTables));
                sessionStorage.setItem('activeMainFilter', filterType);
            }
            // Do not alter manufacturer filter state here; keep filters independent
        });
    });

    // --- Bulk Edit State Restore ---
    if (isBulkEditPage()) {
        restoreBulkEditState();
        // Initialize discount behavior for bulk edit special price modes
        initBulkEditDiscounts();

        // Lazy sorttable: prevent auto-init at load; init on first header click per table
        (function setupLazySort() {
            try {
                var tables = Array.from(document.querySelectorAll('table.sortable'));
                // Cache current sortable tables for other features before altering classes
                // Remove class to avoid sorttable.init wiring thousands of handlers on load
                tables.forEach(function(tbl) {
                    tbl.dataset.lazySortable = '1';
                    tbl.classList.remove('sortable');
                });

                // One-time header click to initialize sorting, then re-dispatch click
                document.addEventListener('click', function(e) {
                    var th = e.target && e.target.closest('th');
                    if (!th) return;
                    var table = th.closest('table');
                    if (!table || table.dataset.lazySortable !== '1') return;

                    // Mark initialized and add class back
                    table.dataset.lazySortable = '0';
                    table.classList.add('sortable');

                    var trigger = function() { try { th.click(); } catch(_) {} };
                    if (window.sorttable && typeof sorttable.makeSortable === 'function') {
                        sorttable.makeSortable(table);
                        setTimeout(trigger, 0);
                    } else {
                        // Wait briefly for sorttable to be available
                        var tries = 0;
                        var iv = setInterval(function() {
                            if (window.sorttable && typeof sorttable.makeSortable === 'function') {
                                clearInterval(iv);
                                sorttable.makeSortable(table);
                                setTimeout(trigger, 0);
                            } else if (++tries > 40) {
                                clearInterval(iv);
                            }
                        }, 50);
                    }
                    e.preventDefault();
                    e.stopPropagation();
                }, true);
            } catch(_) {}
        })();
    }

    // Initialize page-specific behaviors
    if (document.getElementById('updateForm')) {
        initEditProductPage();
    }
    if (document.getElementById('variants-table') && document.getElementById('add-variant-btn')) {
        initAddProductPage();
    }

    // Defer heavy, non-critical work
    schedulePostLoadWork();
});


function storeFilterState() {
    const hiddenTables = [];
    const containers = CACHED.containers || document.querySelectorAll('div.container');
    containers.forEach(container => {
        if (container.style.display === "none") {
            hiddenTables.push(container.getAttribute('data-table'));
        }
    });
    sessionStorage.setItem('hiddenTables', JSON.stringify(hiddenTables));
    // Determine active main filter from visible containers
    const allTypes = Array.from(containers).map(c => c.getAttribute('data-table'));
    const visibleTypes = allTypes.filter(t => !hiddenTables.includes(t));
    let activeMainFilter = 'all';
    if (visibleTypes.length === 1) {
        activeMainFilter = visibleTypes[0];
    } else if (visibleTypes.length === 0) {
        // none visible: treat as 'all' for safety
        activeMainFilter = 'all';
    } else if (visibleTypes.length < allTypes.length) {
        // multiple visible: no single main filter -> use 'all'
        activeMainFilter = 'all';
    }
    sessionStorage.setItem('activeMainFilter', activeMainFilter);
        // Store active manufacturer filter (if any)
        const activeManuBtn = (CACHED.manuBtns ? Array.from(CACHED.manuBtns).find(btn => btn.classList.contains('active')) : document.querySelector('.manufacturer-filter-btn.active'));
        if (activeManuBtn) {
            sessionStorage.setItem('activeManufacturer', activeManuBtn.getAttribute('data-manufacturer'));
        } else {
            sessionStorage.removeItem('activeManufacturer');
        }
}

function restoreFilterState() {
    let hiddenTables = JSON.parse(sessionStorage.getItem('hiddenTables')) || [];
    const containers = CACHED.containers || document.querySelectorAll('div.container');
    const allTypes = Array.from(containers).map(c => c.getAttribute('data-table'));
    // Restore active main filter value
    const activeFilter = sessionStorage.getItem('activeMainFilter') || 'all';

    // If hiddenTables missing but we have an active main filter, reconstruct and persist it
    if ((!hiddenTables || hiddenTables.length === 0) && activeFilter && activeFilter !== 'all') {
        hiddenTables = allTypes.filter(t => t !== activeFilter);
        sessionStorage.setItem('hiddenTables', JSON.stringify(hiddenTables));
    }

    // Apply main filter display strictly from activeFilter
    if (activeFilter && activeFilter !== 'all') {
        filterTables(activeFilter);
    } else {
        showAllTables();
    }

    // Restore active main filter button based on stored value
    (CACHED.filterBtns || document.querySelectorAll('.filter-btn')).forEach(button => {
        if (button.getAttribute('data-table') === activeFilter) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    });
        // Restore manufacturer filter button state and re-apply filter logic
        const activeManufacturer = sessionStorage.getItem('activeManufacturer');
        if (activeManufacturer) {
            const manuBtn = (CACHED.manuBtns ? Array.from(CACHED.manuBtns).find(btn => btn.getAttribute('data-manufacturer') === activeManufacturer) : document.querySelector('.manufacturer-filter-btn[data-manufacturer="' + activeManufacturer + '"]'));
            if (manuBtn && !manuBtn.classList.contains('active')) {
                manuBtn.click();
            }
        } else {
            // No stored manufacturer filter: reveal all cells, but do not clobber
            // server-rendered active button state. If none are active, mark 'all' active.
            (CACHED.productCells || document.querySelectorAll('td[data-manufacturer]')).forEach(cell => (cell.style.visibility = ''));

            var manuBtns = CACHED.manuBtns || document.querySelectorAll('.manufacturer-filter-btn');
            var anyActive = Array.from(manuBtns).some(function(btn){ return btn.classList.contains('active'); });
            if (!anyActive) {
                var showAllBtn = Array.from(manuBtns).find(function(btn){ return btn.getAttribute('data-manufacturer') === 'all'; });
                if (showAllBtn) showAllBtn.classList.add('active');
            }
        }
}

function handleToggleClick() {
    var toggled = sessionStorage.getItem("toggled") === "true";
    sessionStorage.setItem("toggled", !toggled);
    toggleEmptyRows(!toggled);
}

function initialize() {
    // Find numeric inputs only inside stock update forms (avoid styling bulk edit prices/discounts)
    var inputs = document.querySelectorAll('form.stock_input input[type="number"]');
    for (var i = 0; i < inputs.length; i++) {
        // Convert input value to a float and check if it’s zero
        var value = parseFloat(inputs[i].value) || 0;
        inputs[i].classList.toggle('zero-value', value === 0);

        // When the user changes the value, do the same check
        inputs[i].addEventListener('change', function() {
            var newVal = parseFloat(this.value) || 0;
            this.classList.toggle('zero-value', newVal === 0);
        });
    }

    // Title generation is now lazy via delegated handlers (see below)
}

// No-op; titles are created lazily on first hover/focus
function setupInputTitles() {}

// Lazily compute and assign the title for an input in a table cell
function ensureCellTitleForInput(input) {
    if (!input || input.dataset.titleInit === '1') return;
    var cell = input.closest('td, th');
    var row = cell ? cell.closest('tr') : null;
    var table = row ? row.closest('table') : null;
    if (!cell || !row || !table) return;

    var cells = Array.from(row.querySelectorAll('td, th'));
    var idx = cells.indexOf(cell);
    if (idx < 0) idx = 0;

    var headers = table.querySelectorAll('th');
    var header = headers[idx] ? headers[idx].textContent.trim() : '';

    // Heuristic for row label: prefer first two cells: number (or code) + name
    var first = cells[0] ? cells[0].textContent.trim() : '';
    var second = cells[1] ? cells[1].textContent.trim() : '';
    var namePart = second || first || '';
    var numberPart = first && second ? first : ''; // if two fields, treat first as number/code

    var title = '';
    if (numberPart) {
        title = numberPart + ' - ' + namePart + (header ? ' - ' + header : '');
    } else if (namePart) {
        title = namePart + (header ? ' - ' + header : '');
    } else {
        title = header;
    }

    if (title) {
        input.title = title;
        var submitInput = cell.querySelector('input[type="submit"]');
        if (submitInput) submitInput.setAttribute('title', title);
        input.dataset.titleInit = '1';
    }
}

// Delegated lazy title generation on first hover/focus for inputs
document.addEventListener('mouseover', function(evt) {
    var target = evt.target;
    if (target && (target.matches('input[type="number"]') || target.matches('input[type="text"]'))) {
        ensureCellTitleForInput(target);
    }
}, true);

document.addEventListener('focusin', function(evt) {
    var target = evt.target;
    if (target && (target.matches('input[type="number"]') || target.matches('input[type="text"]'))) {
        ensureCellTitleForInput(target);
    }
});

function updateAllStock() {
    var forms = document.querySelectorAll('form.stock_input');
    var pendingRequests = forms.length;

    for (var i = 0; i < forms.length; i++) {
        var form = forms[i];
        var lastRefreshStockInput = form.querySelector('[name="last_refresh_stock"]');
        var submittedStockInput = form.querySelector('[name="submitted_stock"]');

        if (lastRefreshStockInput && submittedStockInput) {
            var lastRefreshStock = parseInt(lastRefreshStockInput.value);
            var submittedStock = parseInt(submittedStockInput.value);

            if (lastRefreshStock !== submittedStock) {
                var formData = new FormData(form);
                var xhr = new XMLHttpRequest();
                xhr.open('POST', form.action, true);
                xhr.onload = function() {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        console.log('Stock updated successfully!');
                        lastRefreshStockInput.value = submittedStock;
                    } else {
                        console.error('Error updating stock');
                    }
                    pendingRequests--;
                    if (pendingRequests === 0) {
                        location.reload();
                    }
                };
                xhr.onerror = function() {
                    console.error('Error updating stock:', xhr.statusText);
                    pendingRequests--;
                    if (pendingRequests === 0) {
                        location.reload();
                    }
                };
                xhr.send(formData);
            } else {
                pendingRequests--;
                if (pendingRequests === 0) {
                    location.reload();
                }
            }
        } else {
            console.error('Missing required input fields in form:', form);
            pendingRequests--;
            if (pendingRequests === 0) {
                location.reload();
            }
        }
    }
}

function updateAllBulkEdit() {
    // --- Store state before AJAX ---
    storeBulkEditState();
    
    console.log('Bulk edit update initiated.');
    var form = document.querySelector('form.bulk-edit');
    if (!form) {
        console.error("Bulk edit form not found.");
        return;
    }
    console.log("Bulk edit form found. Form action:", form.action);
    
    // Extract field name from form action URL (e.g., "/bulk_edit/cannabis_seeds/special_price")
    var actionUrlParts = form.action.split('/');
    var fieldName = actionUrlParts[actionUrlParts.length - 1]; // last part is the field
    console.log("Detected field name from URL:", fieldName);
    
    // Collect all changes into a structured JSON array
    var updates = [];
    var changedProductIds = new Set();
    
    // Process each text/number input in the bulk edit form
    var textInputs = form.querySelectorAll('input[type="text"], input[type="number"]');
    textInputs.forEach(function(input) {
        // Skip discount percent inputs - they are client-side only
        if (input.classList.contains('discount-percent-input')) {
            return;
        }
        
        // Determine the product ID and field from the input name
        var productId, inputFieldName;
        
        // Handle special_price_<ID> naming
        if (input.name.indexOf('special_price_') === 0) {
            productId = input.name.replace('special_price_', '');
            inputFieldName = 'special_price';
        } else {
            // For regular fields, input name is just the product ID
            productId = input.name;
            inputFieldName = fieldName; // Use the field from URL
        }
        
        var hiddenName = "last_refresh_" + input.name;
        var hiddenInput = input.parentElement.querySelector('input[type="hidden"][name="' + hiddenName + '"]');
        
        if (hiddenInput) {
            // Only include if value changed
            if (String(input.value) !== String(hiddenInput.value)) {
                updates.push({
                    id: parseInt(productId),
                    field: inputFieldName,
                    value: input.value === '' ? null : (isNaN(input.value) ? input.value : parseFloat(input.value))
                });
                changedProductIds.add(productId);
                console.log("Changed input detected for product id:", productId, "Field:", inputFieldName, "New value:", input.value);
            }
        } else {
            // No hidden input found, include by default
            updates.push({
                id: parseInt(productId),
                field: inputFieldName,
                value: input.value === '' ? null : (isNaN(input.value) ? input.value : parseFloat(input.value))
            });
            changedProductIds.add(productId);
            console.warn("No hidden original value found for input", input.name);
        }
    });

    // Process checkboxes (e.g., sync flags)
    // Only send sync_flag_* for products that have other changes
    var checkboxes = form.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(function(cb) {
        if (cb.name && cb.name.indexOf('sync_flag_') === 0) {
            var productId = cb.name.replace('sync_flag_', '');
            
            // Only send sync flag if this product has other changes
            if (changedProductIds.has(productId)) {
                updates.push({
                    id: parseInt(productId),
                    field: 'sync_special_price_to_magento',
                    value: cb.checked ? 1 : 0
                });
                console.log('Sync checkbox for changed product appended for', cb.name, 'Value:', cb.checked ? 1 : 0);
            }
            return;
        }

        // For any other checkboxes, only append when changed
        var hiddenName = "last_refresh_" + cb.name;
        var hiddenInput = form.querySelector('input[type="hidden"][name="' + hiddenName + '"]');
        var val = cb.checked ? '1' : '0';
        
        if (hiddenInput) {
            if (hiddenInput.value !== val) {
                updates.push({
                    id: parseInt(cb.name),
                    field: cb.name,
                    value: cb.checked ? 1 : 0
                });
                console.log('Changed checkbox detected for', cb.name, 'New value:', val);
            }
        } else {
            updates.push({
                id: parseInt(cb.name),
                field: cb.name,
                value: cb.checked ? 1 : 0
            });
            console.log('No hidden original value found for checkbox', cb.name);
        }
    });
    
    if (updates.length === 0) {
        console.log('No changes detected.');
        return;
    }
    
    console.log('Total updates collected:', updates.length);
    
    // Send updates in batches
    var batchSize = 100;
    var totalBatches = Math.ceil(updates.length / batchSize);
    var completedBatches = 0;
    
    function sendBatch(batchIndex) {
        var start = batchIndex * batchSize;
        var end = Math.min(start + batchSize, updates.length);
        var batchData = updates.slice(start, end);
        
        var payload = {
            updates: batchData,
            batch: batchIndex,
            total_batches: totalBatches
        };
        
        console.log("Sending batch", batchIndex + 1, "of", totalBatches, "(" + batchData.length + " updates)");
        
        var xhr = new XMLHttpRequest();
        xhr.open('POST', form.action, true);
        xhr.setRequestHeader('Content-Type', 'application/json;charset=UTF-8');
        
        xhr.onload = function() {
            console.log("Batch", batchIndex + 1, "response status:", xhr.status);
            if (xhr.status >= 200 && xhr.status < 300) {
                completedBatches++;
                if (completedBatches === totalBatches) {
                    console.log('All batches completed successfully!');
                    location.reload();
                } else {
                    // Send next batch
                    sendBatch(batchIndex + 1);
                }
            } else {
                console.error('Error in batch', batchIndex + 1, '. Status:', xhr.status);
                console.error('Response:', xhr.responseText);
            }
        };
        
        xhr.onerror = function() {
            console.error('Network error in batch', batchIndex + 1, ':', xhr.statusText);
        };
        
        xhr.send(JSON.stringify(payload));
    }
    
    // Start sending batches
    console.log("Sending updates in", totalBatches, "batch(es)...");
    sendBatch(0);
}

function toggleEmptyRows(shouldHide) {
    var tables = document.querySelectorAll('table');
    for (var t = 0; t < tables.length; t++) {
        var table = tables[t];
        var rows = table.rows;
        for (var r = 1; r < rows.length; r++) {
            var row = rows[r];
            var allEmpty = true;
            var inputs = row.querySelectorAll('input[type="number"]');
            for (var i = 0; i < inputs.length; i++) {
                if (parseInt(inputs[i].value) !== 0) {
                    allEmpty = false;
                    break;
                }
            }
            row.style.display = shouldHide && allEmpty ? 'none' : '';
        }
    }
}

function toggleEmptyColumns() {
    var tables = document.querySelectorAll('table');
    for (var t = 0; t < tables.length; t++) {
        var table = tables[t];
        var headers = table.querySelectorAll('th');
        for (var i = 2; i < headers.length; i++) {
            var allEmpty = true;
            var cells = table.querySelectorAll('td:nth-child(' + (i + 1) + ') input[type="number"]');
            for (var j = 0; j < cells.length; j++) {
                if (parseInt(cells[j].value) !== 0) {
                    allEmpty = false;
                    break;
                }
            }
            var display = allEmpty ? 'none' : '';
            for (var c = 0; c < cells.length; c++) {
                cells[c].style.display = display;
            }
        }
    }
}

function getNameColumnIndex(table) {
    var headers = table.querySelectorAll('th');
    for (var i = 0; i < headers.length; i++) {
        if (headers[i].textContent.trim() === "Name") {
            return i;
        }
    }
    return -1;
}

// Helper: determine if a row is effectively hidden by the manufacturer filter
// A row is considered manufacturer-hidden if it has one or more td[data-manufacturer]
// and ALL such cells are visibility:hidden.
function rowIsManufacturerHidden(row) {
    const productCells = row ? row.querySelectorAll('td[data-manufacturer]') : null;
    if (!productCells || productCells.length === 0) return false;
    for (let i = 0; i < productCells.length; i++) {
        if (productCells[i].style.visibility !== 'hidden') {
            return false;
        }
    }
    return true;
}

function searchTable() {
    var filter = (CACHED.searchInput || document.getElementById("searchInput")).value.toUpperCase().trim();
    var tables = CACHED.tables || document.querySelectorAll("table");
    for (var t = 0; t < tables.length; t++) {
        var table = tables[t];
        var hasVisibleRow = false;
        var rows = table.rows;
        for (var r = 1; r < rows.length; r++) {
            var row = rows[r];
            var rowHasMatch = false;
            var cells = row.cells;
            for (var c = 0; c < cells.length; c++) {
                if (cells[c].textContent.toUpperCase().indexOf(filter) > -1) {
                    rowHasMatch = true;
                    break;
                }
            }
            var manuHidden = rowIsManufacturerHidden(row);
            // Show row only if it matches search AND is not hidden by manufacturer filter
            if (!rowHasMatch || manuHidden) {
                row.style.display = 'none';
            } else {
                row.style.display = '';
                hasVisibleRow = true;
            }
        }
        // If any row remains visible, show table; otherwise hide it
        table.style.display = hasVisibleRow ? "" : "none";
    }
    // localStorage.removeItem('scrollPosition');
}

function clearSearch() {
    document.getElementById('searchInput').value = '';
    localStorage.removeItem('searchInputValue');
    localStorage.removeItem('scrollPosition');
    // Re-apply search with empty filter, which will reveal all rows
    // except those hidden by manufacturer filter or main table filter.
    searchTable();
}

// Toggle showing inline stock forms vs. per-row Edit buttons (non-destructive)
// Now applies to ALL tables/forms on the page regardless of parameter.
var __editMode = false; // global state across the page
function replaceButtons(/* tableName ignored for global behavior */) {
    // Target all stock update forms on the page
    var forms = Array.from(document.querySelectorAll('form.stock_input[action*="/update_stock/"]'));
    if (forms.length === 0) return;

    // Flip global mode
    __editMode = !__editMode;

    // Update all main Edit buttons' visual state
    try {
        var mainEditBtns = document.querySelectorAll('button[onclick^="replaceButtons("]');
        mainEditBtns.forEach(function(btn){
            if (__editMode) {
                btn.classList.add('active');
                btn.setAttribute('aria-pressed', 'true');
            } else {
                btn.classList.remove('active');
                btn.setAttribute('aria-pressed', 'false');
            }
        });
    } catch(_) {}

    // For each form, create a paired per-row Edit button once, then toggle visibility
    forms.forEach(function(form){
        if (!form.__rowEditBtn) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = 'Edit';
            btn.className = 'clear-btn';
            btn.addEventListener('click', function(){
                try {
                    var parts = (form.action || '').split('/');
                    var id = parts[parts.length - 1];
                    var table = parts[parts.length - 2];
                    if (id && table) {
                        window.location.href = '/edit_product/' + encodeURIComponent(table) + '/' + encodeURIComponent(id);
                    }
                } catch(_) {}
            });
            if (form.parentNode) {
                if (form.nextSibling) {
                    form.parentNode.insertBefore(btn, form.nextSibling);
                } else {
                    form.parentNode.appendChild(btn);
                }
            }
            form.__rowEditBtn = btn;
        }

        if (__editMode) {
            form.style.display = 'none';
            form.__rowEditBtn.style.display = '';
        } else {
            form.style.display = '';
            form.__rowEditBtn.style.display = 'none';
        }
    });
}

// Function to update the top value of the sticky table header based on search-container height
function updateTableHeaderTop() {
    var searchContainer = document.getElementById('search-container');
    var tableHeader = document.getElementById('table-header');

    if (searchContainer && tableHeader) {
        var searchContainerHeight = searchContainer.offsetHeight;
        var headerCells = tableHeader.querySelectorAll('th');

        for (var i = 0; i < headerCells.length; i++) {
            headerCells[i].style.top = searchContainerHeight + 'px';
        }
    }
}

// New functions to show all tables or filter by seed type
function showAllTables() {
    const containers = CACHED.containers || document.querySelectorAll('div.container');
    containers.forEach(container => {
        container.style.display = "block";
    });
}

function filterTables(filterType) {
    const containers = CACHED.containers || document.querySelectorAll('div.container');
    containers.forEach(container => {
        const containerType = container.getAttribute('data-table');
        if (containerType === filterType) {
            container.style.display = "block";
        } else {
            container.style.display = "none";
        }
    });
}

// Defer non-critical tasks to idle time
function schedulePostLoadWork() {
    var run = function() {
        // Initial update for sticky header
        updateTableHeaderTop();

        // Initialize zero-value classes and input titles
        initialize();

        // Adjust width of text inputs dynamically using sampling to reduce jank
        const tables = CACHED.tables || document.querySelectorAll('table');
        const MAX_ROWS_TO_MEASURE = 50; // sample only the first N rows per table
        tables.forEach(table => {
            // Only operate on visible tables to avoid unnecessary work
            if (!table || table.offsetParent === null) return;
            // Skip if table has no dynamic-width inputs
            if (!table.querySelector('input.dynamic-width')) return;

            const columns = table.querySelectorAll('tr:first-child td, tr:first-child th');
            const columnWidths = Array(columns.length).fill(0);

            const rows = Array.from(table.querySelectorAll('tr'));
            const limit = Math.min(rows.length, MAX_ROWS_TO_MEASURE);

            // Calculate max width for each column by sampling
            for (let r = 0; r < limit; r++) {
                const row = rows[r];
                const cells = row.querySelectorAll('td, th');
                cells.forEach((cell, index) => {
                    const input = cell.querySelector('input.dynamic-width');
                    if (input) {
                        // Skip special price and discount fields; they have fixed CSS widths
                        if (input.classList.contains('special-price-input') || input.classList.contains('discount-percent-input')) {
                            return;
                        }
                        const contentLength = (input.value || '').length;
                        if (contentLength > columnWidths[index]) columnWidths[index] = contentLength;
                    }
                });
            }

            // Apply the width to all inputs in the same column
            rows.forEach(row => {
                row.querySelectorAll('td, th').forEach((cell, index) => {
                    const input = cell.querySelector('input.dynamic-width');
                    if (input) {
                        // Do not override fixed widths for price/discount inputs
                        if (input.classList.contains('special-price-input') || input.classList.contains('discount-percent-input')) {
                            return;
                        }
                        input.style.width = `${columnWidths[index]}ch`;
                    }
                });
            });
        });

        // After all state (filters, search, layout) has settled, restore row highlight last
        setTimeout(restoreRowHighlight, 0);
    };

    if ('requestIdleCallback' in window) {
        // Give the user a moment to interact before heavy work kicks in
        requestIdleCallback(run, { timeout: 2000 });
    } else {
        setTimeout(run, 250);
    }
}

function scrollToTop() {
    // For better compatibility
    document.documentElement.scrollTop = 0; // For older versions of Firefox
    document.body.scrollTop = 0; // For older versions of Android and other browsers
}


/* --- Bulk Edit Dropdown Functionality --- */
// Allowed attributes for bulk edit per table (alphabetized)
var allowedAttributes = {
    "cannabis_seeds": [
        "available_for_restock",
        "desired_stock",
        "manufacturer",
        "manufacturer_id",
        "magento_sku",
        "magento_stock_updates",
        "manufacturers_collection",
        "name",
        "pack_size",
        "retail_price",
        "special_price",
        "special_price_and_sync",
        "seed_type",
        "stock",
        "storage_location_number",
        "parent_sku",
        "wholesale_price"
    ],
    "growkits": [
        "available_for_restock",
        "desired_stock",
        "magento_sku",
        "magento_stock_updates",
        "manufacturer",
        "manufacturer_id",
        "name",
        "retail_price",
        "special_price",
        "special_price_and_sync",
        "size",
        "stock",
        "parent_sku",
        "wholesale_price"
    ],
    "spores": [
        "available_for_restock",
        "desired_stock",
        "form",
        "manufacturer",
        "manufacturer_id",
        "magento_sku",
        "magento_stock_updates",
        "name",
        "retail_price",
        "special_price",
        "special_price_and_sync",
        "stock",
        "parent_sku",
        "wholesale_price"
    ],
    "cultures": [
        "available_for_restock",
        "desired_stock",
        "form",
        "manufacturer",
        "manufacturer_id",
        "magento_sku",
        "magento_stock_updates",
        "name",
        "retail_price",
        "special_price",
        "special_price_and_sync",
        "size",
        "stock",
        "parent_sku",
        "wholesale_price"
    ],
    "misc": [
        "available_for_restock",
        "desired_stock",
        "manufacturer",
        "manufacturer_id",
        "magento_sku",
        "magento_stock_updates",
        "name",
        "retail_price",
        "special_price",
        "special_price_and_sync",
        "stock",
        "parent_sku",
        "wholesale_price"
    ]
};

function updateAttrOptions() {
    var tableSelect = document.getElementById("tableSelect");
    if (!tableSelect) return;
    var table = tableSelect.value;
    var attrSelect = document.getElementById("attrSelect");
    if (!attrSelect) return;
    
    // Store the current selected attribute value
    var currentAttrValue = attrSelect.value;
    
    // Clear existing options
    attrSelect.innerHTML = "";
    
    var attrs = allowedAttributes[table];
    if (!attrs || !attrs.length) {
      console.error("No allowed attributes found for table: " + table);
      return;
    }
    
    // Create an option element for each allowed attribute
    for (var i = 0; i < attrs.length; i++) {
      var option = document.createElement("option");
      option.value = attrs[i];
      // Convert underscores to spaces and uppercase the text
      option.text = attrs[i].split('_').join(' ').toUpperCase();
      
      // If the current attribute value is still valid, keep it selected
      if (attrs[i] === currentAttrValue) {
        option.selected = true;
      }
      
      attrSelect.appendChild(option);
    }
}
  
  if (document.getElementById("tableSelect")) {
    // When the table dropdown changes, update the attribute dropdown
    document.getElementById("tableSelect").addEventListener("change", updateAttrOptions);
  }
  
  if (document.getElementById("updateSelection")) {
    // When the Update View button is clicked, use the current selections to build the URL
    document.getElementById("updateSelection").addEventListener("click", function() {
      var table = document.getElementById("tableSelect").value;
      var attr = document.getElementById("attrSelect").value;
      window.location.href = "/bulk_edit/" + table + "/" + attr;
    });
  }
  
  // On page load, parse the URL to set the dropdowns
  window.addEventListener("load", function() {
    // Expected URL structure: /bulk_edit/<table>/<field>
    var pathParts = window.location.pathname.split("/");
    if (pathParts.length >= 4) {
      var urlTable = pathParts[2];
      var urlField = pathParts[3];
      var tableSelect = document.getElementById("tableSelect");
      var attrSelect = document.getElementById("attrSelect");
      if (tableSelect) {
        tableSelect.value = urlTable;
      }
      // Populate the attribute dropdown based on the table
      updateAttrOptions();
      if (attrSelect) {
        attrSelect.value = urlField;
      }
    }
  });

// --- Bulk Edit State Helpers ---
function isBulkEditPage() {
    return window.location.pathname.startsWith("/bulk_edit");
}

/* -------------------- Page Specific Initializers -------------------- */
function initBulkEditDiscounts() {
    // Bidirectional calculations for bulk edit special price + discount using delegated listeners
    if (!window.__bulkDelegatedDiscountHandler) {
        document.addEventListener('input', function(evt) {
            var t = evt.target;
            if (!t) return;
            if (t.classList && t.classList.contains('special-price-input')) {
                var retail1 = parseFloat(t.dataset.retail);
                var discField = document.getElementById(t.dataset.discountField);
                if (!discField || !retail1) return;
                if ((t.value || '').trim() === '') {
                    discField.value = '';
                } else {
                    var spVal = parseFloat(t.value);
                    if (!isNaN(spVal)) {
                        var d = ((retail1 - spVal) / retail1 * 100).toFixed(2);
                        discField.value = d;
                    }
                }
            } else if (t.classList && t.classList.contains('discount-percent-input')) {
                var retail2 = parseFloat(t.dataset.retail);
                var dVal = parseFloat(t.value);
                var specialName = t.dataset.specialField;
                var specialField = specialName ? document.querySelector('input[name="' + specialName + '"]') : null;
                if (!specialField || !retail2) return;
                if (!isNaN(dVal) && dVal >= 0 && dVal <= 100) {
                    var sp = (retail2 * (1 - dVal / 100)).toFixed(2);
                    specialField.value = sp;
                } else if (t.value === '') {
                    specialField.value = '';
                }
            }
        }, true);
        window.__bulkDelegatedDiscountHandler = true;
    }
}

function initEditProductPage() {
    // Update form action from /edit_product/... to /update_product/...
    try {
        var currentUrl = window.location.pathname;
        var updatedAction = currentUrl.replace('edit_product', 'update_product');
        var form = document.getElementById('updateForm');
        if (form) form.action = updatedAction;
    } catch (e) { /* noop */ }

    var specialPriceInput = document.querySelector('.special-price-input');
    var discountPercentInput = document.querySelector('.discount-percent-input');

    function calculateDiscount() {
        if (!specialPriceInput || !discountPercentInput) return;
        if (specialPriceInput.value.trim() === '') {
            discountPercentInput.value = '';
            return;
        }
        var retail = parseFloat(specialPriceInput.dataset.retail);
        var specialPrice = parseFloat(specialPriceInput.value);
        if (retail && !isNaN(specialPrice)) {
            var discountPercent = ((retail - specialPrice) / retail) * 100;
            discountPercentInput.value = Math.round(discountPercent * 100) / 100;
        }
    }

    function calculateSpecialPrice() {
        if (!specialPriceInput || !discountPercentInput) return;
        var retail = parseFloat(specialPriceInput.dataset.retail);
        var discountPercent = parseFloat(discountPercentInput.value) || 0;
        if (retail && discountPercent !== undefined && discountPercent !== '') {
            var specialPrice = retail * (1 - (discountPercent / 100));
            specialPriceInput.value = Math.round(specialPrice * 100) / 100;
        } else if (discountPercent === '' || discountPercent === 0) {
            specialPriceInput.value = '';
        }
    }

    // Initialize on load and attach listeners
    calculateDiscount();
    if (specialPriceInput) specialPriceInput.addEventListener('input', calculateDiscount);
    if (discountPercentInput) discountPercentInput.addEventListener('input', calculateSpecialPrice);
}

function initAddProductPage() {
    var addVariantBtn = document.getElementById('add-variant-btn');
    var variantsTable = document.getElementById('variants-table');
    if (!addVariantBtn || !variantsTable) return;

    function cloneClean(elem) {
        var clone = elem.cloneNode(true);
        if (clone.tagName === 'INPUT') {
            if (clone.type === 'checkbox' || clone.type === 'radio') {
                clone.checked = elem.defaultChecked;
            } else {
                clone.value = '';
            }
        } else if (clone.tagName === 'SELECT') {
            clone.selectedIndex = 0; // default first option
        }
        return clone;
    }

    addVariantBtn.addEventListener('click', function() {
        var headerRow = variantsTable.querySelector('thead tr');
        var newTH = document.createElement('th');
        var currentCount = headerRow.children.length - 1; // first TH is blank
        newTH.textContent = 'Variant ' + (currentCount + 1);
        headerRow.appendChild(newTH);

        var rows = variantsTable.querySelectorAll('tbody tr');
        rows.forEach(function(row) {
            var newTD = document.createElement('td');
            var firstVariantCell = row.querySelector('td:nth-child(2)');
            if (firstVariantCell) {
                var baseElem = firstVariantCell.querySelector('input, select');
                if (baseElem) newTD.appendChild(cloneClean(baseElem));
            }
            row.appendChild(newTD);
        });

        setupVariantDiscountCalculations();
    });

    function setupVariantDiscountCalculations() {
        var specialPriceInputs = document.querySelectorAll('.variant-special-price-input');
        var discountPercentInputs = document.querySelectorAll('.variant-discount-percent-input');
        var retailPriceInputs = document.querySelectorAll('input[name="variant_retail_price[]"]');

        retailPriceInputs.forEach(function(retailInput, index) {
            if (index >= specialPriceInputs.length || index >= discountPercentInputs.length) return;
            var specialInput = specialPriceInputs[index];
            var discountInput = discountPercentInputs[index];

            var calculateDiscount = function() {
                if ((specialInput.value || '').trim() === '') {
                    discountInput.value = '';
                    return;
                }
                var retail = parseFloat(retailInput.value) || 0;
                var special = parseFloat(specialInput.value);
                if (retail && !isNaN(special)) {
                    var discount = ((retail - special) / retail) * 100;
                    discountInput.value = Math.round(discount * 100) / 100;
                }
            };

            var calculateSpecial = function() {
                var retail = parseFloat(retailInput.value) || 0;
                var discount = parseFloat(discountInput.value) || 0;
                if (retail && discountInput.value !== '') {
                    var special = retail * (1 - (discount / 100));
                    specialInput.value = Math.round(special * 100) / 100;
                } else if (discountInput.value === '' || discount === 0) {
                    specialInput.value = '';
                }
            };

            specialInput.addEventListener('input', calculateDiscount);
            discountInput.addEventListener('input', calculateSpecial);
            retailInput.addEventListener('input', calculateDiscount);
        });
    }

    // Initial wiring for the first variant column
    setupVariantDiscountCalculations();
}

function storeBulkEditState() {
    // Dropdowns
    var tableSelect = document.getElementById("tableSelect");
    var attrSelect = document.getElementById("attrSelect");
    if (tableSelect && attrSelect) {
        sessionStorage.setItem("bulkEditTable", tableSelect.value);
        sessionStorage.setItem("bulkEditAttr", attrSelect.value);
    }
    // Search input
    var searchInput = document.getElementById("searchInput");
    if (searchInput) {
        sessionStorage.setItem("bulkEditSearch", searchInput.value);
    }
    // Scroll position
    sessionStorage.setItem("bulkEditScroll", window.scrollY);
    // Filter button
    var activeBtn = document.querySelector('.filter-btn.active');
    if (activeBtn) {
        sessionStorage.setItem("bulkEditFilter", activeBtn.getAttribute('data-table'));
    } else {
        sessionStorage.removeItem("bulkEditFilter");
    }
}

function restoreBulkEditState() {
    // Dropdowns
    var tableSelect = document.getElementById("tableSelect");
    var attrSelect = document.getElementById("attrSelect");
    if (tableSelect && sessionStorage.getItem("bulkEditTable")) {
        tableSelect.value = sessionStorage.getItem("bulkEditTable");
        updateAttrOptions();
    }
    if (attrSelect && sessionStorage.getItem("bulkEditAttr")) {
        attrSelect.value = sessionStorage.getItem("bulkEditAttr");
    }
    // Search input
    var searchInput = document.getElementById("searchInput");
    if (searchInput && sessionStorage.getItem("bulkEditSearch")) {
        searchInput.value = sessionStorage.getItem("bulkEditSearch");
        searchTable();
    }
    // Filter button
    var filter = sessionStorage.getItem("bulkEditFilter");
    if (filter) {
        document.querySelectorAll('.filter-btn').forEach(btn => {
            if (btn.getAttribute('data-table') === filter) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        if (filter !== "all") {
            filterTables(filter);
        } else {
            showAllTables();
        }
    }
    // Scroll position
    var scroll = sessionStorage.getItem("bulkEditScroll");
    if (scroll !== null) {
        window.scrollTo(0, parseInt(scroll));
    }
}

function restoreRowHighlight() {
  const key = sessionStorage.getItem('selectedRowKey');
  if (!key) return;

  const esc = (s) => (window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/"/g, '\\"'));
  const row =
    document.querySelector(`tr[data-key="${esc(key)}"]`) ||
    // fallback: locate a form input with that key and climb to <tr>
    document.querySelector(`input[name="item_id"][value="${esc(key)}"]`)?.closest('tr');

  if (!row) return;

  document.querySelectorAll('tr.highlight').forEach(r => r.classList.remove('highlight'));
  row.classList.add('highlight');
  row.scrollIntoView({ block: 'center' });
}