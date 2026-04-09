let customFields = [];
let customFieldValues = {};

// 直接初始化，不依赖 DOMContentLoaded 事件
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function() {
    initCustomFieldsForm();
  });
} else {
  initCustomFieldsForm();
}

function initCustomFieldsForm() {
  loadCustomFields();
  
  const editForm = document.getElementById('edit-form');
  if (editForm) {
    editForm.addEventListener('submit', handleFormSubmit);
  }
}

function loadCustomFields() {
  fetch(window.customFieldsApiBase)
  .then(handleFetchResponse)
  .then(data => {
    customFields = data.data || [];
    
    if (window.editingItemId) {
      loadCustomFieldValues();
    } else {
      renderCustomFieldsForm();
    }
  })
  .catch(err => {
    console.error('加载自定义字段配置失败:', err);
    renderCustomFieldsForm();
  });
}

function loadCustomFieldValues() {
  const resourceType = window.currentModelName === 'hosts' ? 'hosts' : 'vms';
  const valuesApiUrl = `/api/${resourceType}/${window.editingItemId}/custom-field-values`;
  
  fetch(valuesApiUrl)
  .then(handleFetchResponse)
  .then(data => {
    customFieldValues = data.data || {};
    renderCustomFieldsForm();
  })
  .catch(err => {
    console.error('加载自定义字段值失败:', err);
    customFieldValues = {};
    renderCustomFieldsForm();
  });
}

function renderCustomFieldsForm() {
  const container = document.getElementById('custom-fields-form');
  const section = document.getElementById('custom-fields-section');
  
  if (!container || customFields.length === 0) {
    if (section) {
      section.style.display = 'none';
    }
    return;
  }
  
  if (section) {
    section.style.display = 'block';
  }
  
  // 按 sort 排序
  const sortedFields = [...customFields].sort((a, b) => (a.sort || 0) - (b.sort || 0));
  
  container.innerHTML = sortedFields.map(field => {
    const value = customFieldValues[field.id] || null;
    const fieldInputId = `custom-field-${field.id}`;
    const fieldName = `custom_field_${field.id}`;
    
    let inputHtml = '';
    if (field.field_type === 'int') {
      inputHtml = `
        <div class="input-group">
          <input type="number" id="${fieldInputId}" 
                 name="${fieldName}"
                 class="form-input text-xs custom-field-input" 
                 data-field-id="${field.id}" 
                 data-field-type="${field.field_type}"
                 value="${value !== null ? value : ''}">
        </div>
      `;
    } else if (field.field_type === 'varchar') {
      const maxLength = field.field_length || 255;
      inputHtml = `
        <div class="input-group">
          <input type="text" id="${fieldInputId}" 
                 name="${fieldName}"
                 class="form-input text-xs custom-field-input" 
                 data-field-id="${field.id}" 
                 data-field-type="${field.field_type}"
                 maxlength="${maxLength}"
                 value="${value !== null ? value : ''}">
        </div>
      `;
    } else if (field.field_type === 'datetime') {
      const formattedValue = value ? new Date(value).toISOString().slice(0, 16) : '';
      inputHtml = `
        <div class="input-group">
          <input type="datetime-local" id="${fieldInputId}" 
                 name="${fieldName}"
                 class="form-input text-xs custom-field-input" 
                 data-field-id="${field.id}" 
                 data-field-type="${field.field_type}"
                 value="${formattedValue}">
        </div>
      `;
    } else if (field.field_type === 'enum') {
      const options = field.enum_options || [];
      const optionsHtml = options.map(opt => 
        `<option value="${escapeHtml(opt.option_key)}" ${value === opt.option_key ? 'selected' : ''}>${escapeHtml(opt.option_label)}</option>`
      ).join('');
      
      inputHtml = `
        <div class="select-wrapper">
          <select id="${fieldInputId}" 
                  name="${fieldName}"
                  class="form-input text-xs custom-field-input" 
                  data-field-id="${field.id}" 
                  data-field-type="${field.field_type}">
            <option value="">Please select...</option>
            ${optionsHtml}
          </select>
        </div>
      `;
    }
    
    return `
      <tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
        <td class="px-4 py-3 w-1/4 bg-gray-50 border-r border-gray-100">
          <label for="${fieldInputId}" class="block text-sm font-medium text-neutral">
            ${escapeHtml(field.field_name)}
            ${field.is_required === 1 ? '<span class="required-mark">*</span>' : ''}
          </label>
        </td>
        <td class="px-4 py-3">
          <div class="field-wrapper">
            ${inputHtml}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function handleFormSubmit(event) {
  // 现在不需要做任何处理，因为每个自定义字段都有自己的 name 属性
  // 后端会直接从 request.form 中读取 custom_field_<field_id> 的值
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
