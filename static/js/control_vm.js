document.addEventListener('DOMContentLoaded', () => {
  const ipInput = document.getElementById('ip-input');
  const ipErrorMessage = document.getElementById('ip-error-message');
  const searchForm = document.getElementById('vm-search-form');
  const resultCard = document.getElementById('result-card');
  const statusEl   = document.getElementById('vm-status');
  const buttons    = document.querySelectorAll('.vm-btn');
  const controlData = document.getElementById('control-vm-data');
  const getStatusUrl = controlData.dataset.getStatusUrl;
  const powerControlUrl = controlData.dataset.powerControlUrl;
  const csrfToken = controlData.dataset.csrfToken;

  // IP地址验证
  function isValidIPv4(ip) {
    const ipv4Regex = /^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    return ipv4Regex.test(ip);
  }

  // 表单提交验证
  if (searchForm) {
    searchForm.addEventListener('submit', function(event) {
      const ipValue = ipInput.value.trim();
      if (ipValue && !isValidIPv4(ipValue)) {
        event.preventDefault();
        ipErrorMessage.classList.remove('hidden');
        // 添加抖动动画效果
        ipInput.classList.add('animate-shake');
        setTimeout(() => ipInput.classList.remove('animate-shake'), 500);
      } else {
        ipErrorMessage.classList.add('hidden');
      }
    });
  }

  // 如果没有输入 IP 或者结果卡片没渲染，就不执行任何操作
  if (!ipInput.value.trim() || !resultCard) return;

  // 更新状态显示
  function setStatus(status, text) {
    let icon = '';
    if (status === 'running') {
      statusEl.className = 'inline-block px-5 py-2 rounded-full text-base font-medium bg-green-100 text-green-800';
      icon = '<i class="fa fa-check-circle mr-2"></i>';
    } else if (status === 'stopped' || status === 'shut off') {
      statusEl.className = 'inline-block px-5 py-2 rounded-full text-base font-medium bg-gray-100 text-gray-800';
      icon = '<i class="fa fa-power-off mr-2"></i>';
    } else if (status === 'unknown') {
      statusEl.className = 'inline-block px-5 py-2 rounded-full text-base font-medium bg-yellow-100 text-yellow-800';
      icon = '<i class="fa fa-question-circle mr-2"></i>';
    } else { // loading状态
      statusEl.className = 'inline-block px-5 py-2 rounded-full text-base font-medium bg-yellow-100 text-yellow-800';
      icon = '<i class="fa fa-spinner fa-spin mr-2"></i>';
    }
    statusEl.innerHTML = `${icon}${text || status}`;
  }

  // 根据状态激活或禁用按钮
  function updateButtons(status) {
    buttons.forEach(btn => {
      const action = btn.dataset.action;
      btn.classList.add('disabled');
      
      // 当状态为unknown或loading时，禁用所有按钮
      if (status === 'unknown' || status === 'loading') {
        return; // 保持禁用状态
      }
      
      if ((action === 'start' && status !== 'running') ||
          ((action === 'shutdown' || action === 'reboot') && status === 'running')) {
        btn.classList.remove('disabled');
      }
    });
  }

  // 带超时的 fetch
  function fetchWithTimeout(url, options = {}, timeout = 5000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    return fetch(url, { ...options, signal: controller.signal })
      .finally(() => clearTimeout(timer));
  }

  // 拉取 VM 状态
  async function fetchStatus() {
    const ip = ipInput.value.trim();
    if (!ip) return;

    // 显示加载状态
    setStatus('loading...');
    updateButtons('loading');
    await new Promise(r => requestAnimationFrame(r));

    // 设置10秒超时计时器
    let timeoutId = setTimeout(() => {
      // 如果10秒后仍未获取到状态，设置为unknown
      console.log('Timeout fetching status, set to unknown');
      setStatus('unknown');
      updateButtons('unknown');
    }, 10000); // 10秒超时

    try {
      const url = `${getStatusUrl}?ip=${encodeURIComponent(ip)}`;
      const resp = await fetchWithTimeout(url, { method: 'GET' }, 9000); // 比超时短一点，留1秒缓冲

      // 如果成功获取响应，清除超时计时器
      clearTimeout(timeoutId);

      if (!resp.ok) {
        throw new Error(`HTTP error! status: ${resp.status}`);
      }

      const data = await resp.json();
      // 检查返回的状态
      if (['running', 'stopped', 'shut off'].includes(data.status)) {
        setStatus(data.status);
        updateButtons(data.status);
      } else {
        setStatus('unknown');
        updateButtons('unknown');
      }

    } catch (err) {
      console.error('Failed to fetch status:', err);
      // 只有在不是超时的情况下才需要处理，超时已经被计时器处理了
      if (!err.name || err.name !== 'AbortError') {
        clearTimeout(timeoutId);
        setStatus('unknown');
        updateButtons('unknown');
      }
    }
  }

  // 执行开关机操作
  async function handlePowerAction(action) {
    // 获取当前IP地址
    const ip = ipInput.value.trim();
    
    // 显示确认弹窗
    const confirmMessage = `This operation is irreversible. Please verify the IP address and operation type to avoid unnecessary trouble for other colleagues.\n\nIP Address: ${ip}\nOperation: ${action}\n\nConfirm to execute this operation?`;
    
    if (!confirm(confirmMessage)) {
      // 用户点击取消，不执行操作
      return;
    }
    
    buttons.forEach(b => b.classList.add('disabled'));
    setStatus('loading', action === 'start' ? 'booting...' : action === 'shutdown' ? 'shutting down...' : 'rebooting...');

    try {
      const resp = await fetch(powerControlUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ ip: ipInput.value.trim(), action })
      });
      const data = await resp.json();

      // 显示操作结果提示
      if (window.showFlashMessage) {
        window.showFlashMessage(data.message, data.status === 'success' ? 'success' : 'error');
      } else {
        alert(data.message);
      }

      // 延迟刷新状态
      setTimeout(fetchStatus, 2000);
    } catch (err) {
      console.error('Failed to perform action:', err);
      if (window.showFlashMessage) {
        window.showFlashMessage('Operation request failed', 'error');
      } else {
        alert('Operation request failed');
      }
      fetchStatus();
    }
  }

  // 绑定按钮点击事件
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      if (!btn.classList.contains('disabled')) {
        handlePowerAction(btn.dataset.action);
      }
    });
  });

  // 页面加载后立即请求状态
  fetchStatus();
});