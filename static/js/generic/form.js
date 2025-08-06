// static/js/generic_form.js
document.addEventListener('DOMContentLoaded', function() {
  // 初始化Choices.js组件 - 为所有带有choices-select类的select元素
  const choicesElements = document.querySelectorAll('select.choices-select');
  const choicesInstances = [];
  
  choicesElements.forEach(element => {
      const choicesInstance = new Choices(element, {
          searchEnabled: true,
          searchChoices: true,
          searchFields: ['label', 'value'],
          searchResultLimit: 10,
          shouldSort: false,
          fuseOptions: {
          threshold: 0.3,  // 降低阈值以提高匹配精度（0表示完全匹配）
          distance: 500,   // 搜索距离
          minMatchCharLength: 1,  // 最小匹配字符长度
          keys: ['label', 'value']  // 指定搜索的键
          },
          shouldSort: true,  
          position: 'bottom',
          allowHTML: true,
          noResultsText: 'No matching results found',
          noChoicesText: 'No options available',
          itemSelectText: 'Click to select',
          removeItemButton: true,
          duplicateItemsAllowed: false,
          searchPlaceholderValue: 'Search...'
      });
      choicesInstances.push(choicesInstance);
  });

  // ===== 新增：全局页面滚动条样式 =====
  function initGlobalScrollbar() {
    // 创建全局滚动条样式
    const style = document.createElement('style');
    style.textContent = `
      /* 全局滚动条样式（覆盖浏览器默认） */
      html {
        overflow-y: auto; /* 确保页面可滚动 */
      }
      
      /* 滚动条整体宽度 */
      ::-webkit-scrollbar {
        width: 8px;
      }
      
      /* 滚动条轨道 */
      ::-webkit-scrollbar-track {
        background: #f1f1f1; /* 浅灰色轨道 */
        border-radius: 4px;
      }
      
      /* 滚动条滑块 */
      ::-webkit-scrollbar-thumb {
        background: #ccc; /* 灰色滑块 */
        border-radius: 4px;
        transition: background 0.3s ease;
      }
      
      /* 滚动条滑块hover状态 */
      ::-webkit-scrollbar-thumb:hover {
        background: #999; /* 深色滑块 */
      }
      
      /* Firefox浏览器滚动条样式 */
      html {
        scrollbar-width: thin; /* 细滚动条 */
        scrollbar-color: #ccc #f1f1f1; /* 滑块颜色 轨道颜色 */
      }
    `;
    document.head.appendChild(style);

    window.addEventListener('scroll', function() {
      // 计算滚动进度（0-100%）
      const scrollTop = document.documentElement.scrollTop || document.body.scrollTop;
      const scrollHeight = document.documentElement.scrollHeight || document.body.scrollHeight;
      const clientHeight = document.documentElement.clientHeight || window.innerHeight;
      const scrollPercent = (scrollTop / (scrollHeight - clientHeight)) * 100;
    });
  }

  // 初始化全局滚动条
  initGlobalScrollbar();
  
  // 表单提交处理
  const editForm = document.getElementById('edit-form');
  if (editForm) {
    editForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      const form = e.target;
      const formData = new FormData(form);

      try {
        // 显示加载状态
        const submitBtn = document.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa fa-spinner fa-spin mr-1"></i>Saving...';

        // 提交表单
        form.submit();
        return;
        
      } catch (err) {
        console.error(err);
        showNotification('Save failed, please try again later', 'error');
        
        // 恢复按钮状态
        const submitBtn = document.querySelector('button[type="submit"]');
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fa fa-save mr-2"></i>Save';
      }
    });
  }

  // 添加清除按钮功能
  document.querySelectorAll('.clear-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      const targetId = this.getAttribute('data-target');
      const targetInput = document.getElementById(targetId);
      if (targetInput) {
        targetInput.value = '';
        // 如果是select元素，选中第一个选项
        if (targetInput.tagName === 'SELECT') {
          targetInput.selectedIndex = 0;
          // 更新Choices.js实例
          const choicesInstance = choicesInstances.find(instance => instance.passedElement.element.id === 'host-info-select');
          if (choicesInstance) {
              choicesInstance.setChoiceByValue('');
          }
        }
        // 隐藏清除按钮
        this.style.display = 'none';
      }
    });
  });

  // 为所有输入框添加监听，当有内容时显示清除按钮
  document.querySelectorAll('.form-input').forEach(input => {
    // 初始化时检查是否有值
    const clearBtn = input.parentElement.querySelector('.clear-btn');
    if (clearBtn) {
      clearBtn.style.display = input.value ? 'block' : 'none';
    }
    
    // 添加输入事件监听
    input.addEventListener('input', function() {
      const clearBtn = this.parentElement.querySelector('.clear-btn');
      if (clearBtn) {
        clearBtn.style.display = this.value ? 'block' : 'none';
      }
    });
  });
});

// 通知提示函数
function showNotification(message, type = 'info') {
  // 检查是否已存在通知容器
  let notificationContainer = document.getElementById('notification-container');
  if (!notificationContainer) {
    notificationContainer = document.createElement('div');
    notificationContainer.id = 'notification-container';
    notificationContainer.className = 'fixed bottom-4 right-4 space-y-2 z-50';
    document.body.appendChild(notificationContainer);
  }

  // 创建通知元素
  const notification = document.createElement('div');
  notification.className = `px-4 py-2 rounded shadow-lg bg-white border-l-4 ${
    type === 'success' ? 'border-green-500' : 
    type === 'error' ? 'border-red-500' : 'border-blue-500'
  } flex items-center animate-fade-in-down`;
  
  // 设置图标
  let icon = 'info-circle';
  if (type === 'success') icon = 'check-circle';
  if (type === 'error') icon = 'exclamation-circle';
  
  // 设置内容
  notification.innerHTML = `
    <i class="fa fa-${icon} mr-2 ${
      type === 'success' ? 'text-green-500' : 
      type === 'error' ? 'text-red-500' : 'text-blue-500'
    }"></i>
    <span>${message}</span>
  `;
  
  // 添加到容器
  notificationContainer.appendChild(notification);
  
  // 添加动画类
  notification.classList.add('opacity-0', 'translate-y-2', 'transition-all', 'duration-300');
  setTimeout(() => {
    notification.classList.remove('opacity-0', 'translate-y-2');
  }, 10);
  
  // 自动消失
  setTimeout(() => {
    notification.classList.add('opacity-0', 'translate-y-2');
    setTimeout(() => {
      notification.remove();
      // 如果容器为空，移除容器
      if (notificationContainer.children.length === 0) {
        notificationContainer.remove();
      }
    }, 300);
  }, 3000);
}