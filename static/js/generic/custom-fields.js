let customFields = [];
let editingFieldId = null;
let isDeleting = false; // 防止重复删除标志

document.addEventListener('DOMContentLoaded', function() {
  initCustomFields();
});

function initCustomFields() {
  // 使用事件委托方式绑定所有按钮点击
  document.addEventListener('click', function(e) {
    const target = e.target;
    
    // 自定义字段设置按钮
    if (target.closest('#custom-field-settings-btn')) {
      e.preventDefault();
      openCustomFieldSettings();
    }
    
    // Add Field 按钮
    if (target.closest('#add-new-field-btn')) {
      e.preventDefault();
      openFieldForm();
    }
    
    // 关闭自定义字段设置弹窗按钮
    if (target.closest('#close-custom-field-settings') || target.closest('#cancel-custom-field-settings')) {
      e.preventDefault();
      closeModal('custom-field-settings-modal');
    }
    
    // 关闭字段表单弹窗按钮
    if (target.closest('#close-custom-field-form') || target.closest('#cancel-field-form')) {
      e.preventDefault();
      closeModal('custom-field-form-modal');
    }
    
    // 保存字段按钮
    if (target.closest('#save-field-form')) {
      e.preventDefault();
      saveField();
    }
    
    // 添加枚举选项按钮
    if (target.closest('#add-enum-option-btn')) {
      e.preventDefault();
      addEnumOption();
    }
    
    // 编辑字段按钮
    const editBtn = target.closest('[onclick*="openFieldForm"]');
    if (editBtn) {
      const match = editBtn.getAttribute('onclick').match(/openFieldForm\((\d+)\)/);
      if (match) {
        const fieldId = parseInt(match[1]);
        e.preventDefault();
        openFieldForm(fieldId);
      }
    }
    
    // 删除字段按钮
    const deleteBtn = target.closest('.delete-field-btn');
    if (deleteBtn) {
      const fieldId = parseInt(deleteBtn.dataset.fieldId);
      e.preventDefault();
      e.stopPropagation(); // 防止事件冒泡
      confirmDeleteField(fieldId);
    }
  });
  
  // 字段类型变更事件
  document.addEventListener('change', function(e) {
    if (e.target.id === 'form-field-type') {
      handleFieldTypeChange();
    }
  });
}

function openCustomFieldSettings() {
  loadCustomFields();
  openModal('custom-field-settings-modal');
}

function loadCustomFields() {
  fetch(window.customFieldsApiBase, {
    headers: { 'X-CSRFToken': window.csrfToken }
  })
  .then(handleFetchResponse)
  .then(data => {
    customFields = data.data || [];
    renderCustomFieldsList();
  })
  .catch(err => {
    console.error('Failed to load custom fields:', err);
    alert('Failed to load custom fields: ' + err.message);
  });
}

function renderCustomFieldsList() {
  const listContainer = document.getElementById('custom-fields-list');
  if (!listContainer) {
    console.error('custom-fields-list container not found');
    return;
  }
  
  if (customFields.length === 0) {
    listContainer.innerHTML = '<tr><td colspan="5" class="px-3 py-8 text-center text-gray-500">No custom fields yet</td></tr>';
    return;
  }
  
  // 按 sort 排序
  const sortedFields = [...customFields].sort((a, b) => (a.sort || 0) - (b.sort || 0));
  
  listContainer.innerHTML = sortedFields.map(field => `
    <tr class="border-b hover:bg-gray-50">
      <td class="px-3 py-2 text-xs">${escapeHtml(field.field_name)}</td>
      <td class="px-3 py-2 text-xs">${escapeHtml(field.field_type)}</td>
      <td class="px-3 py-2 text-xs">${field.is_required ? '<span class="text-green-600"><i class="fa fa-check"></i></span>' : '-'}</td>
      <td class="px-3 py-2 text-xs">${field.sort}</td>
      <td class="px-3 py-2 text-xs">
        <button class="text-blue-600 hover:text-blue-800 mr-2" onclick="openFieldForm(${field.id}); return false;">
          <i class="fa fa-pencil"></i>
        </button>
        <button class="text-red-600 hover:text-red-800 delete-field-btn" data-field-id="${field.id}">
          <i class="fa fa-trash"></i>
        </button>
      </td>
    </tr>
  `).join('');
}

function openFieldForm(fieldId = null) {
  editingFieldId = fieldId;
  resetFieldForm();
  
  if (fieldId) {
    const field = customFields.find(f => f.id === fieldId);
    
    if (field) {
      document.getElementById('field-form-title').textContent = 'Edit Custom Field';
      document.getElementById('form-field-name').value = field.field_name;
      document.getElementById('form-field-type').value = field.field_type;
      document.getElementById('form-field-type').disabled = true;
      document.getElementById('form-field-length').value = field.field_length || 255;
      document.getElementById('form-is-required').checked = field.is_required === 1;
      document.getElementById('form-default-value').value = field.default_value || '';
      document.getElementById('form-sort').value = field.sort || 0;
      
      handleFieldTypeChange();
      
      if (field.field_type === 'enum' && field.enum_options) {
        field.enum_options.forEach(opt => {
          addEnumOption(opt.option_key, opt.option_label, opt.sort);
        });
      }
    }
  } else {
    document.getElementById('field-form-title').textContent = 'Add Custom Field';
    document.getElementById('form-field-type').disabled = false;
  }
  
  openModal('custom-field-form-modal');
}

function resetFieldForm() {
  document.getElementById('form-field-name').value = '';
  document.getElementById('form-field-type').value = '';
  document.getElementById('form-field-length').value = 255;
  document.getElementById('form-is-required').checked = false;
  document.getElementById('form-default-value').value = '';
  document.getElementById('form-sort').value = 0;
  document.getElementById('enum-options-list').innerHTML = '';
  document.getElementById('form-field-length-container').style.display = 'none';
  document.getElementById('form-enum-options-container').style.display = 'none';
}

function handleFieldTypeChange() {
  const fieldType = document.getElementById('form-field-type').value;
  
  const lengthContainer = document.getElementById('form-field-length-container');
  const enumContainer = document.getElementById('form-enum-options-container');
  
  if (fieldType === 'varchar') {
    lengthContainer.style.display = 'block';
  } else {
    lengthContainer.style.display = 'none';
  }
  
  if (fieldType === 'enum') {
    enumContainer.style.display = 'block';
  } else {
    enumContainer.style.display = 'none';
  }
}

function addEnumOption(key = '', label = '', sort = 0) {
  const container = document.getElementById('enum-options-list');
  if (!container) return;
  
  const optionDiv = document.createElement('div');
  optionDiv.className = 'flex items-center space-x-2';
  optionDiv.innerHTML = `
    <input type="hidden" class="enum-option-key" value="${escapeHtml(key)}">
    <input type="text" class="flex-1 px-2 py-1 border border-gray-300 rounded text-xs enum-option-label" placeholder="Option Label" value="${escapeHtml(label)}">
    <input type="number" class="w-16 px-2 py-1 border border-gray-300 rounded text-xs enum-option-sort" placeholder="Sort" value="${sort}">
    <button type="button" class="text-red-600 hover:text-red-800" onclick="this.parentElement.remove();">
      <i class="fa fa-times"></i>
    </button>
  `;
  
  container.appendChild(optionDiv);
}

function saveField() {
  const fieldName = document.getElementById('form-field-name').value.trim();
  const fieldType = document.getElementById('form-field-type').value;
  const fieldLength = parseInt(document.getElementById('form-field-length').value) || 255;
  const isRequired = document.getElementById('form-is-required').checked ? 1 : 0;
  const defaultValue = document.getElementById('form-default-value').value.trim();
  const sort = parseInt(document.getElementById('form-sort').value) || 0;
  
  if (!fieldName || !fieldType) {
    alert('Please fill in all required fields');
    return;
  }
  
  const enumOptions = [];
  if (fieldType === 'enum') {
    const optionDivs = document.querySelectorAll('#enum-options-list > div');
    optionDivs.forEach(div => {
      const key = div.querySelector('.enum-option-key').value.trim();
      const label = div.querySelector('.enum-option-label').value.trim();
      const optSort = parseInt(div.querySelector('.enum-option-sort').value) || 0;
      if (label) {
        const optData = { option_label: label, sort: optSort };
        if (key) {
          optData.option_key = key;
        }
        enumOptions.push(optData);
      }
    });
    
    if (enumOptions.length === 0) {
      alert('Please add at least one enum option');
      return;
    }
  }
  
  const payload = {
    field_name: fieldName,
    field_type: fieldType,
    field_length: fieldLength,
    is_required: isRequired,
    default_value: defaultValue || null,
    sort: sort
  };
  
  if (fieldType === 'enum') {
    payload.enum_options = enumOptions;
  }
  
  const url = editingFieldId 
    ? `${window.customFieldsApiBase}/${editingFieldId}` 
    : window.customFieldsApiBase;
  const method = editingFieldId ? 'PUT' : 'POST';
  
  fetch(url, {
    method: method,
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': window.csrfToken
    },
    body: JSON.stringify(payload)
  })
  .then(handleFetchResponse)
  .then(data => {
    alert(data.message || 'Field saved successfully');
    closeModal('custom-field-form-modal');
    // 刷新整个页面以显示最新变化
    window.location.reload();
  })
  .catch(err => {
    console.error('Failed to save field:', err);
    alert('Failed to save field: ' + err.message);
  });
}

function confirmDeleteField(fieldId) {
  // 防止重复触发
  if (isDeleting) {
    return;
  }
  
  if (confirm('Delete this custom field? The field data will be hidden but can be restored.')) {
    isDeleting = true;
    deleteField(fieldId);
  }
}

function deleteField(fieldId) {
  fetch(`${window.customFieldsApiBase}/${fieldId}`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': window.csrfToken }
  })
  .then(handleFetchResponse)
  .then(data => {
    alert(data.message || 'Field deleted successfully');
    isDeleting = false;
    // 刷新整个页面以显示最新变化
    window.location.reload();
  })
  .catch(err => {
    console.error('Failed to delete field:', err);
    isDeleting = false;
    alert('Failed to delete field: ' + err.message);
  });
}

function openModal(id) {
  const modal = document.getElementById(id);
  const content = modal?.querySelector('[id$="-content"]');
  if (!modal || !content) {
    console.error('Modal or content not found:', id);
    return;
  }
  
  modal.classList.remove('hidden');
  setTimeout(() => {
    content.classList.remove('scale-95', 'opacity-0');
    content.classList.add('scale-100', 'opacity-100');
  }, 10);
}

function closeModal(id) {
  const modal = document.getElementById(id);
  const content = modal?.querySelector('[id$="-content"]');
  if (!modal || !content) {
    console.error('Modal or content not found:', id);
    return;
  }

  content.classList.remove('scale-100', 'opacity-100');
  content.classList.add('scale-95', 'opacity-0');
  setTimeout(() => modal.classList.add('hidden'), 300);
}

function handleFetchResponse(response) {
  if (!response.ok) {
    return response.json().then(err => { throw new Error(err.message || response.statusText); });
  }
  return response.json();
}

function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
