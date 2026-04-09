// 获取CSRF令牌的辅助函数
function getCsrfToken() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    return metaTag ? metaTag.getAttribute('content') : null;
}

// DOM 加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 切换 Login/Register/Change Password 选项卡
    const loginTab = document.getElementById('login-tab');
    const registerTab = document.getElementById('register-tab');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const changePasswordForm = document.getElementById('change-password-form');
    const messageDiv = document.getElementById('message');
    let currentUserId = null; // 存储当前登录用户ID

    function clearForms() {
        if (loginForm) loginForm.reset();
        if (registerForm) registerForm.reset();
        if (changePasswordForm) changePasswordForm.reset();
    }

    function showLogin() {
        clearForms();
        if (loginTab) {
            loginTab.classList.add('border-primary');
            loginTab.classList.remove('border-transparent');
        }
        if (registerTab) {
            registerTab.classList.add('border-transparent');
            registerTab.classList.remove('border-primary');
        }
        if (loginForm) loginForm.classList.remove('hidden');
        if (registerForm) registerForm.classList.add('hidden');
        if (changePasswordForm) changePasswordForm.classList.add('hidden');
        if (messageDiv) messageDiv.textContent = '';
    }

    function showRegister() {
        clearForms();
        if (registerTab) {
            registerTab.classList.add('border-primary');
            registerTab.classList.remove('border-transparent');
        }
        if (loginTab) {
            loginTab.classList.add('border-transparent');
            loginTab.classList.remove('border-primary');
        }
        if (registerForm) registerForm.classList.remove('hidden');
        if (loginForm) loginForm.classList.add('hidden');
        if (changePasswordForm) changePasswordForm.classList.add('hidden');
        if (messageDiv) messageDiv.textContent = '';
    }

    function showChangePassword(userId) {
        clearForms();
        currentUserId = userId;
        if (loginForm) loginForm.classList.add('hidden');
        if (registerForm) registerForm.classList.add('hidden');
        if (changePasswordForm) changePasswordForm.classList.remove('hidden');
        // 预填当前密码（从登录表单获取）
        const loginPasswordInput = document.getElementById('login-password');
        const oldPasswordInput = document.getElementById('old-password');
        if (loginPasswordInput && oldPasswordInput) {
            oldPasswordInput.value = loginPasswordInput.value;
        }
        if (messageDiv) messageDiv.textContent = 'You must change your password before proceeding';
    }

    loginTab?.addEventListener('click', showLogin);
    registerTab?.addEventListener('click', showRegister);

    // 忘记密码点击事件
    const forgotPasswordLink = document.getElementById('forgot-password');
    forgotPasswordLink?.addEventListener('click', function(e) {
        e.preventDefault();
        alert('Contact your administrator to reset your password');
    });

    // 登录提交处理
    function handleLoginSubmit() {
        const usernameInput = document.getElementById('login-username');
        const passwordInput = document.getElementById('login-password');
        const authForms = document.getElementById('auth-forms');
        
        const username = usernameInput ? usernameInput.value.trim() : '';
        const password = passwordInput ? passwordInput.value : '';
        const loginUrl = authForms ? authForms.dataset.loginUrl : '';

        if (!username || !password) {
            if (messageDiv) messageDiv.textContent = 'Username and password are required';
            return;
        }

        const btn = this;
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Loading...';

        fetch(loginUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCsrfToken()
            },
            body: JSON.stringify({ username, password })
        })
        .then(async response => {
            const data = await response.json();
            
            if (!response.ok) {
                if (data.code === 'MUST_CHANGE_PASSWORD') {
                    if (!data.userId) {
                        if (messageDiv) messageDiv.textContent = 'System error: Missing user ID';
                        return;
                    }
                    showChangePassword(data.userId);
                } else {
                    throw new Error(data.error || `Login failed with status ${response.status}`);
                }
            } else {
                const dashboardUrl = authForms ? authForms.dataset.dashboardUrl : '';
                window.location.href = dashboardUrl;
            }
        })
        .catch(error => {
            console.error('Login error:', error);
            if (messageDiv) messageDiv.textContent = error.message || 'Invalid username or password';
        })
        .finally(() => {
            btn.disabled = false;
            btn.textContent = originalText;
        });
    }

    // 登录提交 - 按钮点击
    const loginSubmitBtn = document.getElementById('login-submit');
    loginSubmitBtn?.addEventListener('click', handleLoginSubmit);

    // 注册提交处理
    function handleRegisterSubmit() {
        if (messageDiv) messageDiv.textContent = '';
        const usernameInput = document.getElementById('reg-username');
        const passwordInput = document.getElementById('reg-password');
        const confirmInput = document.getElementById('reg-password-confirm');
        const authForms = document.getElementById('auth-forms');
        
        const username = usernameInput ? usernameInput.value.trim() : '';
        const password = passwordInput ? passwordInput.value : '';
        const confirm = confirmInput ? confirmInput.value : '';
        const registerUrl = authForms ? authForms.dataset.registerUrl : '';

        if (!username || !password || !confirm) {
            if (messageDiv) messageDiv.textContent = 'All fields are required';
            return;
        }
        
        if (password !== confirm) {
            if (messageDiv) messageDiv.textContent = 'Passwords do not match';
            return;
        }

        // 密码长度验证 - 最短6位
        if (password.length < 6) {
            if (messageDiv) messageDiv.textContent = 'Password must be at least 6 characters long';
            return;
        }

        const btn = this;
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Loading...';

        fetch(registerUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCsrfToken()
            },
            body: JSON.stringify({ username, password })
        })
        .then(async response => {
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || `Registration failed with status ${response.status}`);
            }
            
            // 注册成功后直接跳转到 dashboard（后端已自动登录）
            const dashboardUrl = authForms ? authForms.dataset.dashboardUrl : '';
            window.location.href = dashboardUrl;
        })
        .catch(error => {
            console.error('Register error:', error);
            if (messageDiv) messageDiv.textContent = error.message || 'Registration failed. Please try again.';
        })
        .finally(() => {
            btn.disabled = false;
            btn.textContent = originalText;
        });
    }

    // 注册提交 - 按钮点击
    const registerSubmitBtn = document.getElementById('register-submit');
    registerSubmitBtn?.addEventListener('click', handleRegisterSubmit);

    // 修改密码提交处理
    function handleChangePasswordSubmit() {
        if (messageDiv) messageDiv.textContent = '';
        const oldPasswordInput = document.getElementById('old-password');
        const newPasswordInput = document.getElementById('new-password');
        const confirmPasswordInput = document.getElementById('new-password-confirm');
        const authForms = document.getElementById('auth-forms');
        
        const oldPassword = oldPasswordInput ? oldPasswordInput.value : '';
        const newPassword = newPasswordInput ? newPasswordInput.value : '';
        const confirmPassword = confirmPasswordInput ? confirmPasswordInput.value : '';
        const changePasswordUrl = authForms ? authForms.dataset.changePasswordUrl : '';

        if (!oldPassword || !newPassword || !confirmPassword) {
            if (messageDiv) messageDiv.textContent = 'All fields are required';
            return;
        }

        if (newPassword !== confirmPassword) {
            if (messageDiv) messageDiv.textContent = 'New password and confirm password do not match';
            return;
        }

        // 密码长度验证 - 最短6位
        if (newPassword.length < 6) {
            if (messageDiv) messageDiv.textContent = 'The new password must be at least 6 characters long';
            return;
        }

        // 确保新密码与旧密码不同
        if (newPassword === oldPassword) {
            if (messageDiv) messageDiv.textContent = 'The new password must be different from the current password';
            return;
        }

        const btn = this;
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Changing password...';

        fetch(changePasswordUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCsrfToken()
            },
            body: JSON.stringify({
                user_id: currentUserId,
                old_password: oldPassword,
                new_password: newPassword
            })
        })
        .then(async response => {
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || `Change password failed with status ${response.status}`);
            }
            
            // 密码更新成功，直接跳转到dashboard（后端已自动登录）
            const dashboardUrl = authForms ? authForms.dataset.dashboardUrl : '';
            window.location.href = dashboardUrl;
        })
        .catch(error => {
            console.error('Change password error:', error);
            if (messageDiv) messageDiv.textContent = error.message || 'Password change failed';
        })
        .finally(() => {
            btn.disabled = false;
            btn.textContent = originalText;
        });
    }

    // 修改密码提交 - 按钮点击
    const changePasswordBtn = document.getElementById('change-password-submit');
    changePasswordBtn?.addEventListener('click', handleChangePasswordSubmit);

    // 通用的回车触发按钮功能 - 使用 keydown 事件（更可靠）
    function setupEnterKeyTriggers() {
        // 登录表单
        loginForm?.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.keyCode === 13) {
                e.preventDefault();
                e.stopPropagation();
                if (e.target.tagName === 'INPUT' && loginSubmitBtn) {
                    handleLoginSubmit.call(loginSubmitBtn);
                }
            }
        });

        // 注册表单
        registerForm?.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.keyCode === 13) {
                e.preventDefault();
                e.stopPropagation();
                if (e.target.tagName === 'INPUT' && registerSubmitBtn) {
                    handleRegisterSubmit.call(registerSubmitBtn);
                }
            }
        });

        // 修改密码表单
        changePasswordForm?.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.keyCode === 13) {
                e.preventDefault();
                e.stopPropagation();
                if (e.target.tagName === 'INPUT' && changePasswordBtn) {
                    handleChangePasswordSubmit.call(changePasswordBtn);
                }
            }
        });
    }

    // 设置全场景回车触发
    setupEnterKeyTriggers();
});
