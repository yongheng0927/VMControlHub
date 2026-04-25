// 使用命名空间避免与 list.js 中的函数冲突
const CustomFieldsModule = {
  customFields: [],
  editingFieldId: null,
  isDeleting: false,
  needsPageRefresh: false,

  init: function() {
    document.addEventListener('DOMContentLoaded', function() {
      CustomFieldsModule.initCustomFields();
    });
  },

  initCustomFields: function() {
    document.addEventListener('click', function(e) {
      const target = e.target;
      
      if (target.closest('#custom-field-settings-btn')) {
        e.preventDefault();
        CustomFieldsModule.openCustomFieldSettings();
      }
      
      if (target.closest('#add-new-field-btn')) {
        e.preventDefault();
        CustomFieldsModule.openFieldForm();
      }
      
      if (target.closest('#close-custom-field-settings') || target.closest('#cancel-custom-field-settings')) {
        e.preventDefault();
        CustomFieldsModule.closeModal('custom-field-settings-modal');
      }
      
      if (target.closest('#close-custom-field-form') || target.closest('#cancel-field-form')) {
        e.preventDefault();
        CustomFieldsModule.closeModal('custom-field-form-modal');
      }
      
      if (target.closest('#save-field-form')) {
        e.preventDefault();
        CustomFieldsModule.saveField();
      }
      
      if (target.closest('#add-enum-option-btn')) {
        e.preventDefault();
        CustomFieldsModule.addEnumOption();
      }
      
      const editBtn = target.closest('[onclick*="openFieldForm"]');
      if (editBtn) {
        const match = editBtn.getAttribute('onclick').match(/openFieldForm\((\d+)\)/);
        if (match) {
          const fieldId = parseInt(match[1]);
          e.preventDefault();
          CustomFieldsModule.openFieldForm(fieldId);
        }
      }
      
      const deleteBtn = target.closest('.delete-field-btn');
      if (deleteBtn) {
        const fieldId = parseInt(deleteBtn.dataset.fieldId);
        e.preventDefault();
        e.stopPropagation();
        CustomFieldsModule.confirmDeleteField(fieldId);
      }
    });
    
    document.addEventListener('change', function(e) {
      if (e.target.id === 'form-field-type') {
        CustomFieldsModule.handleFieldTypeChange();
      }
    });
  },

  openCustomFieldSettings: function() {
    CustomFieldsModule.loadCustomFields();
    // 使用 list.js 中定义的全局 openModal 函数
    window.openModal('custom-field-settings-modal');
  },

  loadCustomFields: function() {
    fetch(window.customFieldsApiBase, {
      headers: { 'X-CSRFToken': window.csrfToken }
    })
    .then(CustomFieldsModule.handleFetchResponse)
    .then(data => {
      CustomFieldsModule.customFields = data.data || [];
      CustomFieldsModule.renderCustomFieldsList();
    })
    .catch(err => {
      console.error('Failed to load custom fields:', err);
      alert('Failed to load custom fields: ' + err.message);
    });
  },

  renderCustomFieldsList: function() {
    const listContainer = document.getElementById('custom-fields-list');
    if (!listContainer) {
      console.error('custom-fields-list container not found');
      return;
    }
    
    if (CustomFieldsModule.customFields.length === 0) {
      listContainer.innerHTML = '<tr><td colspan="5" class="px-3 py-8 text-center text-gray-500">No custom fields yet</td></tr>';
      return;
    }
    
    const sortedFields = [...CustomFieldsModule.customFields].sort((a, b) => (a.sort || 0) - (b.sort || 0));
    
    listContainer.innerHTML = sortedFields.map(field => `
      <tr class="border-b hover:bg-gray-50">
        <td class="px-3 py-2 text-xs">${CustomFieldsModule.escapeHtml(field.field_name)}</td>
        <td class="px-3 py-2 text-xs">${CustomFieldsModule.escapeHtml(field.field_type)}</td>
        <td class="px-3 py-2 text-xs">${field.is_required ? '<span class="text-green-600"><i class="fa fa-check"></i></span>' : '-'}</td>
        <td class="px-3 py-2 text-xs">${field.sort}</td>
        <td class="px-3 py-2 text-xs">
          <button class="text-blue-600 hover:text-blue-800 mr-2" onclick="CustomFieldsModule.openFieldForm(${field.id}); return false;">
            <i class="fa fa-pencil"></i>
          </button>
          <button class="text-red-600 hover:text-red-800 delete-field-btn" data-field-id="${field.id}">
            <i class="fa fa-trash"></i>
          </button>
        </td>
      </tr>
    `).join('');
  },

  openFieldForm: function(fieldId = null) {
    CustomFieldsModule.editingFieldId = fieldId;
    CustomFieldsModule.resetFieldForm();
    
    if (fieldId) {
      const field = CustomFieldsModule.customFields.find(f => f.id === fieldId);
      
      if (field) {
        document.getElementById('field-form-title').textContent = 'Edit Custom Field';
        document.getElementById('form-field-name').value = field.field_name;
        document.getElementById('form-field-type').value = field.field_type;
        document.getElementById('form-field-type').disabled = true;
        document.getElementById('form-field-length').value = field.field_length || 255;
        document.getElementById('form-is-required').checked = field.is_required === 1;
        document.getElementById('form-default-value').value = field.default_value || '';
        document.getElementById('form-sort').value = field.sort || 0;
        
        CustomFieldsModule.handleFieldTypeChange();
        
        if (field.field_type === 'enum' && field.enum_options) {
          field.enum_options.forEach(opt => {
            CustomFieldsModule.addEnumOption(opt.option_key, opt.option_label, opt.sort);
          });
        }
      }
    } else {
      document.getElementById('field-form-title').textContent = 'Add Custom Field';
      document.getElementById('form-field-type').disabled = false;
    }
    
    // 使用 list.js 中定义的全局 openModal 函数
    window.openModal('custom-field-form-modal');
  },

  resetFieldForm: function() {
    document.getElementById('form-field-name').value = '';
    document.getElementById('form-field-type').value = '';
    document.getElementById('form-field-length').value = 255;
    document.getElementById('form-is-required').checked = false;
    document.getElementById('form-default-value').value = '';
    document.getElementById('form-sort').value = 0;
    document.getElementById('enum-options-list').innerHTML = '';
    document.getElementById('form-field-length-container').style.display = 'none';
    document.getElementById('form-enum-options-container').style.display = 'none';
  },

  handleFieldTypeChange: function() {
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
  },

  addEnumOption: function(key = '', label = '', sort = 0) {
    const container = document.getElementById('enum-options-list');
    if (!container) return;
    
    const optionDiv = document.createElement('div');
    optionDiv.className = 'flex items-center space-x-2';
    optionDiv.innerHTML = `
      <input type="hidden" class="enum-option-key" value="${CustomFieldsModule.escapeHtml(key)}">
      <input type="text" class="flex-1 px-2 py-1 border border-gray-300 rounded text-xs enum-option-label" placeholder="Option Label" value="${CustomFieldsModule.escapeHtml(label)}">
      <input type="number" class="w-16 px-2 py-1 border border-gray-300 rounded text-xs enum-option-sort" placeholder="Sort" value="${sort}">
      <button type="button" class="text-red-600 hover:text-red-800" onclick="this.parentElement.remove();">
        <i class="fa fa-times"></i>
      </button>
    `;
    
    container.appendChild(optionDiv);
  },

  saveField: function() {
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
    
    const url = CustomFieldsModule.editingFieldId 
      ? `${window.customFieldsApiBase}/${CustomFieldsModule.editingFieldId}` 
      : window.customFieldsApiBase;
    const method = CustomFieldsModule.editingFieldId ? 'PUT' : 'POST';
    
    fetch(url, {
      method: method,
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': window.csrfToken
      },
      body: JSON.stringify(payload)
    })
    .then(CustomFieldsModule.handleFetchResponse)
    .then(data => {
      alert(data.message || 'Field saved successfully');
      CustomFieldsModule.needsPageRefresh = true;
      CustomFieldsModule.loadCustomFields();
      CustomFieldsModule.resetFieldForm();
    })
    .catch(err => {
      console.error('Failed to save field:', err);
      alert('Failed to save field: ' + err.message);
    });
  },

  confirmDeleteField: function(fieldId) {
    if (CustomFieldsModule.isDeleting) {
      return;
    }
    
    if (confirm('Delete this custom field? The field data will be hidden but can be restored.')) {
      CustomFieldsModule.isDeleting = true;
      CustomFieldsModule.deleteField(fieldId);
    }
  },

  deleteField: function(fieldId) {
    fetch(`${window.customFieldsApiBase}/${fieldId}`, {
      method: 'DELETE',
      headers: { 'X-CSRFToken': window.csrfToken }
    })
    .then(CustomFieldsModule.handleFetchResponse)
    .then(data => {
      alert(data.message || 'Field deleted successfully');
      CustomFieldsModule.isDeleting = false;
      CustomFieldsModule.needsPageRefresh = true;
      CustomFieldsModule.loadCustomFields();
    })
    .catch(err => {
      console.error('Failed to delete field:', err);
      CustomFieldsModule.isDeleting = false;
      alert('Failed to delete field: ' + err.message);
    });
  },

  closeModal: function(id) {
    const modal = document.getElementById(id);
    const content = modal?.querySelector('[id$="-content"]');
    if (!modal || !content) {
      console.error('Modal or content not found:', id);
      return;
    }

    content.classList.remove('scale-100', 'opacity-100');
    content.classList.add('scale-95', 'opacity-0');
    
    setTimeout(() => {
      modal.classList.add('hidden');
      
      if (id === 'custom-field-settings-modal' && CustomFieldsModule.needsPageRefresh) {
        window.location.reload();
      }
    }, 300);
  },

  handleFetchResponse: function(response) {
    if (!response.ok) {
      return response.json().then(err => { throw new Error(err.message || response.statusText); });
    }
    return response.json();
  },

  escapeHtml: function(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
};

// 初始化模块
CustomFieldsModule.init();
