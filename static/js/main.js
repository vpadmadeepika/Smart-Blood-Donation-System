/**
 * Smart Blood Donation Management System - Core Frontend Scripts
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Mobile Menu Toggle
  const mobileToggle = document.getElementById('mobileNavToggle');
  const navMenu = document.getElementById('navMenu');
  if (mobileToggle && navMenu) {
    mobileToggle.addEventListener('click', () => {
      navMenu.classList.toggle('active');
    });
  }

  // 2. Modals Management
  const modalOpenBtns = document.querySelectorAll('[data-modal-target]');
  const modalCloseBtns = document.querySelectorAll('[data-modal-close]');

  modalOpenBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = btn.getAttribute('data-modal-target');
      const targetModal = document.getElementById(targetId);
      if (targetModal) {
        targetModal.classList.add('active');
      }
    });
  });

  modalCloseBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal-overlay');
      if (modal) {
        modal.classList.remove('active');
      }
    });
  });

  // Close modal when clicking on backdrop
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.classList.remove('active');
      }
    });
  });

  // 3. Notification Dropdown & AJAX mark as read
  const notifToggle = document.getElementById('notifToggle');
  const notifDropdown = document.getElementById('notifDropdown');
  if (notifToggle && notifDropdown) {
    notifToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      notifDropdown.style.display = notifDropdown.style.display === 'block' ? 'none' : 'block';
    });

    document.addEventListener('click', (e) => {
      if (!notifDropdown.contains(e.target) && e.target !== notifToggle) {
        notifDropdown.style.display = 'none';
      }
    });
  }

  // 4. One-Click Demo Account Autofill on Login Page
  const demoButtons = document.querySelectorAll('.demo-login-btn');
  const emailInput = document.getElementById('loginEmail');
  const passwordInput = document.getElementById('loginPassword');

  demoButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const email = btn.getAttribute('data-email');
      const password = btn.getAttribute('data-password');
      if (emailInput && passwordInput) {
        emailInput.value = email;
        passwordInput.value = password;
        // Visual feedback
        emailInput.style.borderColor = '#10b981';
        passwordInput.style.borderColor = '#10b981';
      }
    });
  });

  // 5. Interactive Blood Compatibility Explorer (Home Page)
  const compatSelect = document.getElementById('compatGroupSelect');
  const compatResultList = document.getElementById('compatResultList');
  const compatGiveList = document.getElementById('compatGiveList');
  
  const recipientMap = {
    'O-': ['O-'],
    'O+': ['O-', 'O+'],
    'A-': ['O-', 'A-'],
    'A+': ['O-', 'O+', 'A-', 'A+'],
    'B-': ['O-', 'B-'],
    'B+': ['O-', 'O+', 'B-', 'B+'],
    'AB-': ['O-', 'A-', 'B-', 'AB-'],
    'AB+': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
  };

  const donorMap = {
    'O-': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],
    'O+': ['O+', 'A+', 'B+', 'AB+'],
    'A-': ['A-', 'A+', 'AB-', 'AB+'],
    'A+': ['A+', 'AB+'],
    'B-': ['B-', 'B+', 'AB-', 'AB+'],
    'B+': ['B+', 'AB+'],
    'AB-': ['AB-', 'AB+'],
    'AB+': ['AB+']
  };

  if (compatSelect && compatResultList && compatGiveList) {
    const updateCompatDisplay = (bg) => {
      const receiveFrom = recipientMap[bg] || [];
      const donateTo = donorMap[bg] || [];

      compatResultList.innerHTML = receiveFrom.map(g => `<span class="compat-pill">${g}</span>`).join(' ');
      compatGiveList.innerHTML = donateTo.map(g => `<span class="compat-pill">${g}</span>`).join(' ');
    };

    compatSelect.addEventListener('change', (e) => {
      updateCompatDisplay(e.target.value);
    });
  }

  // 6. Show / Hide Password Toggle Helper
  const passwordToggles = document.querySelectorAll('.password-toggle-btn');
  passwordToggles.forEach(toggle => {
    toggle.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = toggle.getAttribute('data-target');
      const input = document.getElementById(targetId);
      const icon = toggle.querySelector('i');
      if (input) {
        if (input.type === 'password') {
          input.type = 'text';
          if (icon) {
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
          }
        } else {
          input.type = 'password';
          if (icon) {
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
          }
        }
      }
    });
  });

  // 7. Dynamic Role Selector on Registration Page (Toggles Custom Fields for Donor, Recipient, Hospital, NGO, Blood Bank)
  const roleSelect = document.getElementById('regRoleSelect');
  const donorFields = document.getElementById('donorFields');
  const recipientFields = document.getElementById('recipientFields');
  const hospitalFields = document.getElementById('hospitalFields');
  const ngoFields = document.getElementById('ngoFields');
  const bloodBankFields = document.getElementById('bloodBankFields');
  const roleBadge = document.getElementById('roleInfoBadge');

  if (roleSelect) {
    const handleRoleChange = () => {
      const selected = roleSelect.value;
      
      // Reset all custom role containers
      if (donorFields) donorFields.style.display = (selected === 'donor') ? 'block' : 'none';
      if (recipientFields) recipientFields.style.display = (selected === 'recipient') ? 'block' : 'none';
      if (hospitalFields) hospitalFields.style.display = (selected === 'hospital') ? 'block' : 'none';
      if (ngoFields) ngoFields.style.display = (selected === 'ngo') ? 'block' : 'none';
      if (bloodBankFields) bloodBankFields.style.display = (selected === 'blood_bank') ? 'block' : 'none';

      // Update role description badge
      if (roleBadge) {
        const descriptions = {
          'donor': '🩸 Volunteer Donor: Register to receive urgent donation matches, manage your availability, and track donation recovery intervals.',
          'recipient': '🩹 Recipient / Patient: Request emergency or scheduled blood units and track live matching in real-time.',
          'hospital': '🩺 Hospital / ER: Submit critical trauma transfusion requests and coordinate directly with matched donors & blood banks.',
          'ngo': '🤝 NGO / Community Foundation: Coordinate blood donation camps, organize awareness drives, and support patient access.',
          'blood_bank': '🏢 Blood Bank / Storage Center: Manage blood inventory batches, monitor expiry warnings, and record blood collection & issue transactions.'
        };
        roleBadge.textContent = descriptions[selected] || '';
      }
    };
    roleSelect.addEventListener('change', handleRoleChange);
    handleRoleChange(); // Initialize on page load
  }

  // 8. Auto-dismiss alerts after 5 seconds
  setTimeout(() => {
    document.querySelectorAll('.alert-dismissible').forEach(alert => {
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 300);
    });
  }, 5000);
});

// Helper for mark single notification as read via API
function markNotifRead(notifId, el) {
  fetch(`/api/notifications/${notifId}/read`, { method: 'POST' })
    .then(res => res.json())
    .then(data => {
      if (data.success && el) {
        el.style.opacity = '0.5';
        const badge = document.querySelector('.notif-badge');
        if (badge) {
          let count = parseInt(badge.textContent, 10);
          if (count > 1) {
            badge.textContent = count - 1;
          } else {
            badge.remove();
          }
        }
      }
    });
}
