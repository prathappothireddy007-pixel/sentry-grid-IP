/**
 * SentryGrid – Authentication JavaScript (auth.js)
 * ===================================================
 * Handles user sign in, registration, role selection,
 * HTML5 Geolocation API auto-detection, and demo viva buttons.
 * CSA4310 – Internet Programming
 */

// Switch between Login and Register tabs
function switchAuthTab(tab) {
    const loginForm = document.getElementById('form-login');
    const registerForm = document.getElementById('form-register');
    const loginTabBtn = document.getElementById('tab-login-btn');
    const registerTabBtn = document.getElementById('tab-register-btn');
    const alertBox = document.getElementById('auth-alert');

    if (alertBox) alertBox.classList.add('d-none');

    if (tab === 'login') {
        loginForm.classList.remove('d-none');
        registerForm.classList.add('d-none');
        loginTabBtn.classList.add('active');
        registerTabBtn.classList.remove('active');
    } else {
        loginForm.classList.add('d-none');
        registerForm.classList.remove('d-none');
        loginTabBtn.classList.remove('active');
        registerTabBtn.classList.add('active');
    }
}

// Quick Demo credential filling for academic demonstration
function fillCredentials(username, password) {
    switchAuthTab('login');
    document.getElementById('login-username').value = username;
    document.getElementById('login-password').value = password;
    showToast('info', `Filled demo credentials for ${username}. Click Sign In to proceed.`);
}

// HTML5 Geolocation API capture during citizen registration
function captureRegistrationGPS() {
    const label = document.getElementById('reg-gps-label');
    const latInput = document.getElementById('reg-lat');
    const lonInput = document.getElementById('reg-lon');
    const localityInput = document.getElementById('reg-locality');

    if (!navigator.geolocation) {
        showToast('error', 'Geolocation API is not supported by your browser.');
        return;
    }

    if (label) label.textContent = 'Locating GPS satellites...';

    navigator.geolocation.getCurrentPosition(
        function(position) {
            const lat = position.coords.latitude.toFixed(6);
            const lon = position.coords.longitude.toFixed(6);
            if (latInput) latInput.value = lat;
            if (lonInput) lonInput.value = lon;
            if (label) label.textContent = `GPS Captured: (${lat}, ${lon})`;
            if (localityInput && !localityInput.value) {
                localityInput.value = 'Local Coordinates Locked';
            }
            showToast('success', 'GPS coordinates successfully locked for disaster routing!');
        },
        function(error) {
            let msg = 'Could not retrieve GPS coordinates.';
            if (error.code === error.PERMISSION_DENIED) {
                msg = 'GPS permission denied. Please enter locality manually.';
            }
            if (label) label.textContent = 'GPS Unavailable (Manual Entry)';
            showToast('warning', msg);
        },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
    );
}

// Asynchronous Login Form Submission
function handleLogin(e) {
    e.preventDefault();

    const username = $('#login-username').val().trim();
    const password = $('#login-password').val();
    const btn = $('#btn-login-submit');
    const alertBox = $('#auth-alert');

    if (!username || !password) {
        showToast('error', 'Please enter both username and password.');
        return;
    }

    btn.prop('disabled', true);
    btn.find('.btn-text').addClass('d-none');
    btn.find('.spinner-sm').removeClass('d-none');
    alertBox.addClass('d-none');

    $.ajax({
        url: '/api/login',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            username: username,
            password: password
        }),
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                showToast('success', response.message);
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 600);
            } else {
                btn.prop('disabled', false);
                btn.find('.btn-text').removeClass('d-none');
                btn.find('.spinner-sm').addClass('d-none');
                alertBox.removeClass('d-none alert-success').addClass('alert-danger').text(response.message);
            }
        },
        error: function(xhr) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            let err = 'Unable to connect to SentryGrid server.';
            if (xhr.responseJSON && xhr.responseJSON.message) {
                err = xhr.responseJSON.message;
            }
            alertBox.removeClass('d-none alert-success').addClass('alert-danger').text(err);
            showToast('error', err);
        }
    });
}

// Asynchronous Registration Form Submission
function handleRegister(e) {
    e.preventDefault();

    const username = $('#reg-username').val().trim();
    const fullName = $('#reg-fullname').val().trim();
    const email = $('#reg-email').val().trim();
    const password = $('#reg-password').val();
    const role = $('#reg-role').val();
    const phone = $('#reg-phone').val().trim();
    const locality = $('#reg-locality').val().trim();
    const lat = $('#reg-lat').val();
    const lon = $('#reg-lon').val();
    const btn = $('#btn-reg-submit');
    const alertBox = $('#auth-alert');

    // Validation
    if (username.length < 3) {
        showToast('error', 'Username must be at least 3 characters.');
        return;
    }
    if (password.length < 6) {
        showToast('error', 'Password must be at least 6 characters.');
        return;
    }

    btn.prop('disabled', true);
    btn.find('.btn-text').addClass('d-none');
    btn.find('.spinner-sm').removeClass('d-none');
    alertBox.addClass('d-none');

    $.ajax({
        url: '/api/register',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            username: username,
            full_name: fullName,
            email: email,
            password: password,
            role: role,
            phone: phone,
            locality: locality,
            latitude: lat ? parseFloat(lat) : null,
            longitude: lon ? parseFloat(lon) : null
        }),
        dataType: 'json',
        success: function(response) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            if (response.success) {
                showToast('success', response.message);
                switchAuthTab('login');
                $('#login-username').val(username);
                $('#login-password').val(password);
                alertBox.removeClass('d-none alert-danger').addClass('alert-success').text('Account created! Please sign in.');
            }
        },
        error: function(xhr) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            let err = 'Registration request failed.';
            if (xhr.responseJSON && xhr.responseJSON.message) {
                err = xhr.responseJSON.message;
            }
            alertBox.removeClass('d-none alert-success').addClass('alert-danger').text(err);
            showToast('error', err);
        }
    });
}
