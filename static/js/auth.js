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
        loginForm.reset();
        registerForm.reset();
        changePasswordForm.reset();
    }

    function showLogin() {
        clearForms();
        loginTab.classList.add('border-primary');
        loginTab.classList.remove('border-transparent');
        registerTab.classList.add('border-transparent');
        registerTab.classList.remove('border-primary');
        loginForm.classList.remove('hidden');
        registerForm.classList.add('hidden');
        changePasswordForm.classList.add('hidden');
        messageDiv.textContent = '';
    }

    function showRegister() {
        clearForms();
        registerTab.classList.add('border-primary');
        registerTab.classList.remove('border-transparent');
        loginTab.classList.add('border-transparent');
        loginTab.classList.remove('border-primary');
        registerForm.classList.remove('hidden');
        loginForm.classList.add('hidden');
        changePasswordForm.classList.add('hidden');
        messageDiv.textContent = '';
    }

    function showChangePassword(userId) {
        clearForms();
        currentUserId = userId;
        loginForm.classList.add('hidden');
        registerForm.classList.add('hidden');
        changePasswordForm.classList.remove('hidden');
        // 预填当前密码（从登录表单获取）
        const currentPassword = document.getElementById('login-password').value;
        document.getElementById('old-password').value = currentPassword;
        messageDiv.textContent = 'You must change your password before proceeding';
    }

    loginTab?.addEventListener('click', showLogin);
    registerTab?.addEventListener('click', showRegister);

    // 忘记密码点击事件
    const forgotPasswordLink = document.getElementById('forgot-password');
    forgotPasswordLink?.addEventListener('click', function(e) {
        e.preventDefault();
        alert('Contact your administrator to reset your password');
    });

    // 登录提交
    const loginSubmitBtn = document.getElementById('login-submit');
    loginSubmitBtn?.addEventListener('click', function() {
        const username = document.getElementById('login-username').value.trim();
        const password = document.getElementById('login-password').value;
        const loginUrl = document.getElementById('auth-forms').dataset.loginUrl;

        if (!username || !password) {
            messageDiv.textContent = 'Username and password are required';
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
                        messageDiv.textContent = 'System error: Missing user ID';
                        return;
                    }
                    showChangePassword(data.userId);
                } else {
                    throw new Error(data.error || `Login failed with status ${response.status}`);
                }
            } else {
                window.location.href = document.getElementById('auth-forms').dataset.dashboardUrl;
            }
        })
        .catch(error => {
            messageDiv.textContent = error.message || 'Invalid username or password';
        })
        .finally(() => {
            btn.disabled = false;
            btn.textContent = originalText;
        });
    });

    // 注册提交
    const registerSubmitBtn = document.getElementById('register-submit');
    registerSubmitBtn?.addEventListener('click', function() {
        messageDiv.textContent = '';
        const username = document.getElementById('reg-username').value.trim();
        const password = document.getElementById('reg-password').value;
        const confirm = document.getElementById('reg-password-confirm').value;
        const registerUrl = document.getElementById('auth-forms').dataset.registerUrl;

        if (!username || !password || !confirm) {
            messageDiv.textContent = 'All fields are required';
            return;
        }
        
        if (password !== confirm) {
            messageDiv.textContent = 'Passwords do not match';
            return;
        }

        // 密码长度验证 - 最短6位
        if (password.length < 6) {
            messageDiv.textContent = 'Password must be at least 6 characters long';
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
            
            showLogin();
            messageDiv.textContent = 'Registration successful. Please login.';
        })
        .catch(error => {
            messageDiv.textContent = error.message || 'Registration failed. Please try again.';
        })
        .finally(() => {
            btn.disabled = false;
            btn.textContent = originalText;
        });
    });

    // 修改密码提交
    const changePasswordBtn = document.getElementById('change-password-submit');
    changePasswordBtn?.addEventListener('click', function() {
        messageDiv.textContent = '';
        const oldPassword = document.getElementById('old-password').value;
        const newPassword = document.getElementById('new-password').value;
        const confirmPassword = document.getElementById('new-password-confirm').value;
        const changePasswordUrl = document.getElementById('auth-forms').dataset.changePasswordUrl;

        if (!oldPassword || !newPassword || !confirmPassword) {
            messageDiv.textContent = 'All fields are required';
            return;
        }

        if (newPassword !== confirmPassword) {
            messageDiv.textContent = 'New password and confirm password do not match';
            return;
        }

        // 密码长度验证 - 最短6位
        if (newPassword.length < 6) {
            messageDiv.textContent = 'The new password must be at least 6 characters long';
            return;
        }

        // 确保新密码与旧密码不同
        if (newPassword === oldPassword) {
            messageDiv.textContent = 'The new password must be different from the current password';
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
            
            showLogin();
            // 清空所有密码字段
            document.getElementById('login-password').value = '';
            document.getElementById('old-password').value = '';
            document.getElementById('new-password').value = '';
            document.getElementById('new-password-confirm').value = '';
            messageDiv.textContent = 'Password change successful. Please use the new password to login.';
        })
        .catch(error => {
            messageDiv.textContent = error.message || 'Password change failed';
        })
        .finally(() => {
            btn.disabled = false;
            btn.textContent = originalText;
        });
    });
});