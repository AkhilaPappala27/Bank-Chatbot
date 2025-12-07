document.addEventListener("DOMContentLoaded", () => {


  // ==========================
  // Chat Popup Open & Close
  // ==========================
  const startChat = document.getElementById("startChatBtn");
  const overlay = document.getElementById("chat-overlay");
  const closeChat = document.getElementById("closeChat");

  if (startChat) {
    startChat.addEventListener("click", () => {
      overlay.style.display = "flex";             // Show Chat Modal
      document.body.style.overflow = "hidden";    // Disable page scroll
    });
  }

  if (closeChat) {
    closeChat.addEventListener("click", () => {
      overlay.style.display = "none";             // Close Chat Modal
      document.body.style.overflow = "auto";      // Enable scroll again
    });
  }

});
