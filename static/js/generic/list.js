let currentFilterField = null;
let currentVisibleFields = window.currentVisibleFields || [];
const defaultColumns = window.defaultColumns || [];
const csrfToken = window.csrfToken || '';
let selectedIds = new Set();

// 提取通用 URL 参数更新函数
function updateUrlParams(modifier) {
  const urlParams = new URLSearchParams(window.location.search);
  modifier(urlParams);
  // 不重置页码，除非是搜索或过滤操作
  if (!modifier.toString().includes('sort') && !modifier.toString().includes('order')) {
    urlParams.set('page', 1);
  }
  window.location.search = urlParams.toString();
}

// 页面加载完成后绑定事件
document.addEventListener('DOMContentLoaded', function() {
  // 全局搜索
  const searchBtn = document.getElementById('search-btn');
  const globalSearchInput = document.getElementById('global-search');
  if (searchBtn && globalSearchInput) {
    searchBtn.addEventListener('click', function() {
      const searchTerm = globalSearchInput.value.trim();
      updateUrlParams(urlParams => {
        urlParams.set('page', 1);
        if (searchTerm) {
          urlParams.set('search', searchTerm);
        } else {
          urlParams.delete('search');
        }
      });
    });
    globalSearchInput.addEventListener('keyup', e => e.key === 'Enter' && searchBtn.click());
  }

  // 重置按钮
  const resetBtn = document.getElementById('reset-btn');
  if (resetBtn) {
    resetBtn.addEventListener('click', function() {
      if (globalSearchInput) globalSearchInput.value = '';
      const url = new URL(window.location);
      url.search = '';
      window.location.href = url.href;
    });
  }

  // 过滤按钮
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      currentFilterField = this.getAttribute('data-field');
      const fieldObj = allFields.find(f => f.db_field === currentFilterField);
      if (fieldObj) {
        document.getElementById('current-field').textContent = fieldObj.label;
      }
      loadFilterOptions(currentFilterField);
      openModal('filter-modal');
    });
  });

  // 绑定过滤模态框的按钮事件
  const applyFilterBtn = document.getElementById('apply-filter');
  if (applyFilterBtn) {
    applyFilterBtn.addEventListener('click', applyFilter);
  }
  const clearFilterBtn = document.getElementById('clear-filter');
  if (clearFilterBtn) {
    clearFilterBtn.addEventListener('click', clearFilter);
  }

  // 关闭模态框
  ['filter-modal', 'table-set-modal', 'bulk-edit-modal', 'import-modal'].forEach(id => {
    const modal = document.getElementById(id);
    if (modal) {
      modal.addEventListener('click', e => {
        if (e.target === modal) closeModal(id);
      });
      const closeBtn = modal.querySelector(`#close-${id.replace('-modal', '')}`);
      if (closeBtn) {
        closeBtn.addEventListener('click', () => closeModal(id));
      }
      const cancelBtn = modal.querySelector(`#cancel-${id.replace('-modal', '')}`);
      if (cancelBtn) {
        cancelBtn.addEventListener('click', () => closeModal(id));
      }
    }
  });

  // 表格设置
  const tableSetBtn = document.getElementById('table-set-btn');
  if (tableSetBtn) {
    tableSetBtn.addEventListener('click', () => {
      initTableSettings();
      openModal('table-set-modal');
    });
  }
  
  // 批量选择
  const selectAllCheckbox = document.getElementById('select-all-rows');
  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', () => {
      const rowCheckboxes = document.querySelectorAll('.row-checkbox');
      rowCheckboxes.forEach(cb => {
        cb.checked = selectAllCheckbox.checked;
        updateSelectedIds(cb.dataset.id, cb.checked);
      });
      updateBulkActionsBar();
    });
  }

  document.querySelectorAll('.row-checkbox').forEach(cb => {
    cb.addEventListener('change', () => {
      updateSelectedIds(cb.dataset.id, cb.checked);
      updateBulkActionsBar();
    });
  });

  // 批量操作
  const clearSelectionBtn = document.getElementById('clear-selection-btn');
  if (clearSelectionBtn) {
    clearSelectionBtn.addEventListener('click', clearSelection);
  }
  const bulkEditBtn = document.getElementById('bulk-edit-btn');
  if (bulkEditBtn) {
    bulkEditBtn.addEventListener('click', () => openModal('bulk-edit-modal'));
  }
  const bulkDeleteBtn = document.getElementById('bulk-delete-btn');
  if (bulkDeleteBtn) {
    bulkDeleteBtn.addEventListener('click', bulkDelete);
  }
  
  // 批量编辑表单
  const bulkEditField = document.getElementById('bulk-edit-field');
  if(bulkEditField) {
    bulkEditField.addEventListener('change', handleBulkEditFieldChange);
  }
  const applyBulkEditBtn = document.getElementById('apply-bulk-edit');
  if (applyBulkEditBtn) {
    applyBulkEditBtn.addEventListener('click', applyBulkEdit);
  }

// 导入数据功能
const importBtn = document.getElementById('import-data-btn');
if (importBtn) {
    importBtn.addEventListener('click', () => {
        // 动态填充必填字段
        const requiredFieldsList = document.getElementById('required-fields-list');
        requiredFieldsList.innerHTML = '';
        
        const requiredFieldLabels = window.formFields
            .filter(field => field.required)
            .map(field => field.label);

        if (requiredFieldLabels.length > 0) {
            requiredFieldLabels.forEach(fieldLabel => {
                const li = document.createElement('li');
                li.textContent = fieldLabel;
                requiredFieldsList.appendChild(li);
            });
        } else {
            requiredFieldsList.innerHTML = '<li>This model has no required fields.</li>';
        }

        // 打开模态框
        openModal('import-modal');

        // 在模态框打开后，再绑定其内部元素的事件
        const confirmImportBtn = document.getElementById('confirm-import');
        const fileInput = document.getElementById('import-file-input');
        const feedbackDiv = document.getElementById('import-feedback');
        const customUploadBtn = document.getElementById('custom-upload-btn');
        const fileNameSpan = document.getElementById('file-name');

        customUploadBtn.addEventListener('click', () => {
            fileInput.click();
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                fileNameSpan.textContent = fileInput.files[0].name;
            } else {
                fileNameSpan.textContent = 'No file chosen';
            }
            feedbackDiv.innerHTML = '';
            if (confirmImportBtn) confirmImportBtn.disabled = false;
        });

        confirmImportBtn.addEventListener('click', () => {
            const file = fileInput.files[0];
            if (!file) {
                feedbackDiv.innerHTML = '<span class="text-red-500">Please select a file first.</span>';
                return;
            }

            const formData = new FormData();
            formData.append('file', file);

            confirmImportBtn.disabled = true;
            confirmImportBtn.textContent = 'Importing...';
            feedbackDiv.innerHTML = '<span class="text-blue-500">Uploading and processing file, please wait...</span>';

            fetch(`/api/${window.currentModelName}/import`, {
                method: 'POST',
                headers: { 'X-CSRFToken': window.csrfToken },
                body: formData
            })
            .then(async response => {
                const data = await response.json();
                if (!response.ok) {
                    let errorHtml = `<span class="text-red-500">${data.error}</span>`;
                    if (data.details && Array.isArray(data.details)) {
                        errorHtml += '<ul class="list-disc list-inside mt-2 text-red-700">';
                        data.details.forEach(detail => { errorHtml += `<li>${detail}</li>`; });
                        errorHtml += '</ul>';
                    }
                    feedbackDiv.innerHTML = errorHtml;
                } else {
                    feedbackDiv.innerHTML = `<span class="text-green-500">${data.message}</span>`;
                    setTimeout(() => window.location.reload(), 1500);
                }
            })
            .catch(error => {
                feedbackDiv.innerHTML = `<span class="text-red-500">Unknown error: ${error.message}</span>`;
            })
            .finally(() => {
                confirmImportBtn.disabled = false;
                confirmImportBtn.textContent = 'Start Import';
            });
        });
    });
}
  
  // 初始化批量操作栏状态
  updateBulkActionsBar();

  // "详情" 按钮事件委托
  document.body.addEventListener('click', function(event) {
    const detailsButton = event.target.closest('.details-button');
    if (detailsButton) {
      const container = detailsButton.closest('.details-container');
      if (container) {
        const content = container.querySelector('.details-content');
        detailsButton.classList.add('hidden');
        content.classList.remove('hidden');
      }
    }

    const closeButton = event.target.closest('.close-details-button');
    if (closeButton) {
      const container = closeButton.closest('.details-container');
      if (container) {
        const content = container.querySelector('.details-content');
        const button = container.querySelector('.details-button');
        content.classList.add('hidden');
        button.classList.remove('hidden');
      }
    }
  });
});

// 模态框辅助函数
function openModal(id) {
  const modal = document.getElementById(id);
  const content = modal?.querySelector('[id$="-content"]');
  if (!modal || !content) return;
  
  modal.classList.remove('hidden');
  setTimeout(() => {
    content.classList.remove('scale-95', 'opacity-0');
    content.classList.add('scale-100', 'opacity-100');
  }, 10);
}

function closeModal(id) {
  const modal = document.getElementById(id);
  const content = modal?.querySelector('[id$="-content"]');
  if (!modal || !content) return;

  content.classList.remove('scale-100', 'opacity-100');
  content.classList.add('scale-95', 'opacity-0');
  setTimeout(() => modal.classList.add('hidden'), 300);
}

// 批量选择逻辑
function updateSelectedIds(id, isSelected) {
  if (isSelected) {
    selectedIds.add(id);
  } else {
    selectedIds.delete(id);
  }
}

function updateBulkActionsBar() {
  const bar = document.getElementById('bulk-actions-bar');
  const countSpan = document.getElementById('selected-count');
  const editBtn = document.getElementById('bulk-edit-btn');
  const deleteBtn = document.getElementById('bulk-delete-btn');

  // 只检查必要的核心元素，删除按钮不存在不影响编辑按钮
  if (!bar || !countSpan || !editBtn) return;

  const count = selectedIds.size;
  countSpan.textContent = `Selected ${count} items`;
  
  bar.classList.add('visible'); // 确保操作栏始终可见

  // 处理编辑按钮状态
  if (count > 0) {
    editBtn.disabled = false;
    editBtn.removeAttribute('disabled');
  } else {
    editBtn.disabled = true;
  }

  // 只在删除按钮存在时处理其状态
  if (deleteBtn) {
    if (count > 0) {
      deleteBtn.disabled = false;
      deleteBtn.removeAttribute('disabled');
    } else {
      deleteBtn.disabled = true;
    }
  }

  // 更新全选复选框状态
  const selectAllCheckbox = document.getElementById('select-all-rows');
  const rowCheckboxes = document.querySelectorAll('.row-checkbox');
  if (selectAllCheckbox) {
    selectAllCheckbox.checked = count > 0 && count === rowCheckboxes.length;
    selectAllCheckbox.indeterminate = count > 0 && count < rowCheckboxes.length;
  }
}
    

function clearSelection() {
  document.querySelectorAll('.row-checkbox:checked').forEach(cb => cb.checked = false);
  const selectAllCheckbox = document.getElementById('select-all-rows');
  if(selectAllCheckbox) selectAllCheckbox.checked = false;
  selectedIds.clear();
  updateBulkActionsBar();
}

// 批量操作
function bulkDelete() {
  if (selectedIds.size === 0) return;
  if (confirm(`Are you sure you want to delete the selected ${selectedIds.size} items?`)) {
    fetch(`/${window.currentModelName}/bulk-delete`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({ ids: Array.from(selectedIds) })
    })
    .then(handleFetchResponse)
    .then(() => {
      alert('Bulk delete successful');
      window.location.reload();
    })
    .catch(err => alert(`Bulk delete failed: ${err.message}`));
  }
}

function handleBulkEditFieldChange() {
  const fieldName = this.value;
  const container = document.getElementById('bulk-edit-value-container');
  container.innerHTML = '';
  if (!fieldName) {
    container.classList.add('hidden');
    return;
  }
  
  const field = window.formFields.find(f => f.name === fieldName);
  if (!field) return;

  let inputHtml = '';
  if (field.type === 'boolean') {
    // For boolean, use a checkbox
    inputHtml = `<input type="checkbox" name="value" class="h-5 w-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500">`;
  } else if (field.type === 'select' && field.options) {
    const options = field.options.map(opt => `<option value="${opt}">${opt}</option>`).join('');
    inputHtml = `<select name="value" class="w-full px-3 py-2 border rounded-lg text-sm"><option value="">-- Select --</option>${options}</select>`;
  } else {
    // For other types like text, number, etc.
    const inputType = field.type === 'number' ? 'number' : 'text';
    inputHtml = `<input type="${inputType}" name="value" class="w-full px-3 py-2 border rounded-lg text-sm">`;
  }
  
  const label = field.type === 'boolean' ? `<label for="value" class="ml-2">${field.label}</label>` : `<label class="block text-sm font-medium text-gray-700 mb-1">New Value</label>`;
  
  if (field.type === 'boolean') {
      container.innerHTML = `<div class="flex items-center">${inputHtml}${label}</div>`;
  } else {
      container.innerHTML = `${label}${inputHtml}`;
  }
  container.classList.remove('hidden');
}

function applyBulkEdit() {
  const form = document.getElementById('bulk-edit-form');
  const field = form.elements.field.value;
  const valueElement = form.elements.value;

  if (!field) {
    alert('Please select a field to edit');
    return;
  }
  
  if (!valueElement) {
    alert('Please input a new value');
    return;
  }
  
  const value = valueElement.type === 'checkbox' ? valueElement.checked : valueElement.value;
  
  if (selectedIds.size === 0) return;
  
  fetch(`/${window.currentModelName}/bulk-edit`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken
    },
    body: JSON.stringify({
      ids: Array.from(selectedIds),
      field: field,
      value: value
    })
  })
  .then(handleFetchResponse)
  .then(() => {
    alert('Bulk edit successful');
    window.location.reload();
  })
  .catch(err => alert(`Bulk edit failed: ${err.message}`));
}

// 表格排序设置
function initTableSettings() {
  const columnList = document.getElementById('column-list');
  columnList.innerHTML = '';
  
  let currentOrder = currentVisibleFields.slice();
  let allFieldNames = allFields.map(f => f.db_field);
  
  // 添加未显示的列到末尾
  allFieldNames.forEach(fieldName => {
    if(!currentOrder.includes(fieldName)) {
      currentOrder.push(fieldName);
    }
  });

  currentOrder.forEach(fieldName => {
    const field = allFields.find(f => f.db_field === fieldName);
    if(!field) return;

    const isVisible = currentVisibleFields.includes(field.db_field);
    const item = document.createElement('div');
    item.className = 'config-table-item';
    item.dataset.field = field.db_field;
    item.innerHTML = `
      <input type="checkbox" class="w-4 h-4 text-primary focus:ring-primary rounded mr-3 column-toggle" ${isVisible ? 'checked' : ''}>
      <span class="flex-grow">${field.label}</span>
      <i class="fa fa-bars text-gray-400 cursor-grab drag-handle"></i>
    `;
    columnList.appendChild(item);
  });
  
  // 搜索
  const columnSearch = document.getElementById('column-search');
  if(columnSearch) {
    columnSearch.addEventListener('input', e => {
        const term = e.target.value.toLowerCase();
        columnList.querySelectorAll('.config-table-item').forEach(item => {
        item.style.display = item.textContent.toLowerCase().includes(term) ? 'flex' : 'none';
      });
    });
  }

  // 重置
  const resetFieldsBtn = document.getElementById('reset-fields');
  if(resetFieldsBtn) {
    resetFieldsBtn.addEventListener('click', () => {
        fetch(`/${window.currentModelName}/api/save-table-settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ visible_columns: window.defaultColumns })
        })
        .then(handleFetchResponse)
        .then(() => {
            alert('Table settings have been reset to default values');
            updateUrlParams(params => {
                params.delete('visible_columns');
            });
        })
        .catch(err => alert(`Reset failed: ${err.message}`));
    });
  }

  // 保存
  const saveTableSetBtn = document.getElementById('save-table-set');
  if(saveTableSetBtn) saveTableSetBtn.onclick = saveTableSettings;
  
  // 拖拽排序
  if (typeof Sortable !== 'undefined') {
    new Sortable(columnList, {
      handle: '.drag-handle',
      animation: 150,
    });
  }
}

function saveTableSettings() {
  const columnList = document.getElementById('column-list');
  const visibleColumns = Array.from(columnList.querySelectorAll('.config-table-item'))
                              .filter(item => item.querySelector('.column-toggle').checked)
                              .map(item => item.dataset.field);

  const allColumnsInOrder = Array.from(columnList.querySelectorAll('.config-table-item'))
                                .map(item => item.dataset.field);

  // 我们需要保存的是所有列的顺序，以及哪些是可见的。
  // 一个更健壮的方法是只保存可见列的顺序。
  const orderedVisibleColumns = allColumnsInOrder.filter(field => visibleColumns.includes(field));

      fetch(`/${window.currentModelName}/api/save-table-settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
    body: JSON.stringify({ visible_columns: orderedVisibleColumns })
      })
  .then(handleFetchResponse)
      .then(() => {
        alert('Table settings have been saved');
    updateUrlParams(params => {
      params.set('visible_columns', orderedVisibleColumns.join(','));
    });
  })
  .catch(err => alert(`Save failed: ${err.message}`));
}

// 过滤逻辑
function loadFilterOptions(field) {
    const optionsContainer = document.getElementById('filter-options');
    optionsContainer.innerHTML = '<div class="text-center py-4">Loading...</div>';

    const params = new URLSearchParams(window.location.search);
    params.set('field', field);
    
    fetch(`/${window.currentModelName}/api/filter-options?${params.toString()}`)
        .then(handleFetchResponse)
        .then(data => {
            optionsContainer.innerHTML = '';
            const currentFilter = new URLSearchParams(window.location.search).get(field);
            const selectedValues = currentFilter ? new Set(currentFilter.split(',')) : new Set();

            data.options.forEach(option => {
                const isSelected = selectedValues.has(String(option.value));
                optionsContainer.insertAdjacentHTML('beforeend', `
                    <div class="flex items-center py-2 hover:bg-gray-50 rounded-lg px-2 filter-option">
                        <input type="checkbox" id="filter-${field}-${option.value}" value="${option.value}"
                               class="filter-checkbox w-4 h-4 text-primary" ${isSelected ? 'checked' : ''}>
                        <label for="filter-${field}-${option.value}" class="ml-2 text-sm">${option.label || '(空)'}</label>
                    </div>
                `);
            });
            
            // 设置全选checkbox逻辑
            setupSelectAll();
            
            // 设置实时过滤搜索
            setupFilterSearch(data.options);
        })
        .catch(err => optionsContainer.innerHTML = `<div class="text-red-500 p-4">${err.message}</div>`);
}

// 设置过滤搜索功能
function setupFilterSearch(allOptions) {
    const filterSearch = document.getElementById('filter-search');
    const optionsContainer = document.getElementById('filter-options');
    const allFilterOptions = optionsContainer.querySelectorAll('.filter-option');
    
    if (filterSearch) {
        // 清除之前的事件监听器
        filterSearch.value = '';
        
        // 添加input事件实现实时过滤
        filterSearch.addEventListener('input', function() {
            const searchTerm = this.value.trim().toLowerCase();
            
            // 如果搜索框为空，显示所有选项
            if (!searchTerm) {
                allFilterOptions.forEach(option => {
                    option.style.display = '';
                });
                return;
            }
            
            // 使用前缀匹配过滤选项
            allFilterOptions.forEach(option => {
                const label = option.querySelector('label').textContent.toLowerCase();
                // 使用包含匹配
                if (label.includes(searchTerm)) {
                    option.style.display = '';
                } else {
                    option.style.display = 'none';
                }
            });
        });
    }
}

function setupSelectAll() {
  const selectAll = document.getElementById('select-all');
  const checkboxes = document.querySelectorAll('.filter-checkbox');
  
  if(selectAll) {
    selectAll.onchange = () => checkboxes.forEach(cb => cb.checked = selectAll.checked);
  }
  
  checkboxes.forEach(cb => cb.onchange = () => {
    const checkedCount = document.querySelectorAll('.filter-checkbox:checked').length;
    if(selectAll) {
        selectAll.checked = checkedCount === checkboxes.length;
        selectAll.indeterminate = checkedCount > 0 && checkedCount < checkboxes.length;
    }
  });
}

// applyFilter 函数
function applyFilter() {
  if (!currentFilterField) return;
  const selected = Array.from(document.querySelectorAll('.filter-checkbox:checked')).map(cb => cb.value);
  
  updateUrlParams(params => {
      if (selected.length > 0) {
          params.set(currentFilterField, selected.join(','));
      } else {
          params.delete(currentFilterField);
      }
      params.set('page', 1);
  });
  
  closeModal('filter-modal');
}

function clearFilter() {
    if (!currentFilterField) return;
    updateUrlParams(params => {
        params.delete(currentFilterField);
        params.set('page', 1);
    });
    closeModal('filter-modal');
}

// 通用Fetch响应处理
function handleFetchResponse(response) {
  if (!response.ok) {
    return response.json().then(err => { throw new Error(err.message || response.statusText); });
  }
  return response.json();
}