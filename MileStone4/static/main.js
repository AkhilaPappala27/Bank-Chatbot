document.addEventListener("DOMContentLoaded", () => {

  // ==========================
  // Chat Popup Open & Close
  // ==========================
  const startChat = document.getElementById("startChatBtn");
  const overlay = document.getElementById("chat-overlay");
  const closeChat = document.getElementById("closeChat");

  if (startChat) {
    startChat.addEventListener("click", () => {
      overlay.style.display = "flex";
      document.body.style.overflow = "hidden";
    });
  }

  if (closeChat) {
    closeChat.addEventListener("click", () => {
      overlay.style.display = "none";
      document.body.style.overflow = "auto";
    });
  }


  // ==========================
  // USER / ADMIN LOGIN SWITCH
  // ==========================

  const userBtn = document.getElementById("userBtn");
  const adminBtn = document.getElementById("adminBtn");

  const mainLabel = document.getElementById("mainLabel");
  const mainInput = document.getElementById("mainInput");
  const forgotLink = document.getElementById("forgotLink");
  const signupBlock = document.getElementById("signupBlock");
  const roleInput = document.getElementById("roleInput");

  if (userBtn && adminBtn) {

      function showUser() {
          userBtn.classList.add("active-role");
          adminBtn.classList.remove("active-role");

          mainLabel.textContent = "Account Number or Phone Number";
          mainInput.placeholder = "Enter account number";
          mainInput.name = "account";

          forgotLink.style.display = "inline";
          signupBlock.style.display = "block";
          roleInput.value = "user";
      }

      function showAdmin() {
          adminBtn.classList.add("active-role");
          userBtn.classList.remove("active-role");

          mainLabel.textContent = "Admin Email";
          mainInput.placeholder = "Enter admin email";
          mainInput.name = "admin_email";

          forgotLink.style.display = "none";
          signupBlock.style.display = "none";
          roleInput.value = "admin";
      }

      userBtn.addEventListener("click", showUser);
      adminBtn.addEventListener("click", showAdmin);

      if (INITIAL_ROLE === "admin") {
        showAdmin();
      } else {
        showUser();
      }
  }

});
