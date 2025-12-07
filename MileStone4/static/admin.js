// ======================== PAGE SWITCHING ========================
document.addEventListener("DOMContentLoaded", () => {

    const navItems = document.querySelectorAll(".nav-item");
    const sections = document.querySelectorAll(".page-section");

    navItems.forEach(item => {
        item.addEventListener("click", () => {

            // Remove active class from all
            navItems.forEach(n => n.classList.remove("active"));
            sections.forEach(s => s.classList.remove("active"));

            // Activate clicked item
            item.classList.add("active");

            // Show related section
            const pageId = item.getAttribute("data-page");
            document.getElementById(pageId).classList.add("active");

            // Load training data ONLY when this tab opens
            if (pageId === "training") loadTrainingData();

            // Load user queries ONLY when this tab opens
            if (pageId === "queries") loadUserQueries();

            if (pageId === "faqs") loadFaqs();

            if (pageId === "analytics") {
                if (!window.analyticsLoaded) {
                    loadAnalytics();
                    window.analyticsLoaded = true;
                }
            }
            // Load admin data into settings UI on open
            if (pageId === "settings") {
                fetch("/get_admin_data")
                    .then(res => res.json())
                    .then(data => {
                        document.getElementById("profileName").value = data.name;
                        document.getElementById("profileEmail").value = data.email;
                        document.getElementById("emailNotifyToggle").checked = data.email_notifications;
        });
}

        });
    });

    // Load training data immediately on dashboard open
    loadTrainingData();
});



// ======================== TRAINING DATA FUNCTIONS ========================

// ---------- RENDER ONE TRAINING ROW ----------
function renderRow(r) {
    let examples = r.examples || [];
    let exHtml = "";

    if (examples.length === 0) {
        exHtml = "<em>-</em>";
    } else {
        for (let i = 0; i < Math.min(2, examples.length); i++) {
            exHtml += `"${examples[i]}"<br>`;
        }
        if (examples.length > 2) {
            exHtml += `<small style='color:#475569;'>+${examples.length - 2} more</small>`;
        }
    }

    let entHtml = "";
    if (r.entities) {
        r.entities.split(",")
            .map(e => e.trim())
            .filter(Boolean)
            .forEach(e => {
                entHtml += `<span style="
                    display:inline-block;
                    background:#22d3ee;
                    color:#083344;
                    padding:6px 10px;
                    border-radius:999px;
                    margin-right:6px;
                    font-size:13px;">
                    ${e}
                </span>`;
            });
    }

    let statusHtml = (r.status === "trained")
        ? `<span style="background:#bbf7d0; color:#15803d; padding:6px 12px; border-radius:999px;">trained</span>`
        : `<span style="background:#fef3c7; color:#b45309; padding:6px 12px; border-radius:999px;">pending</span>`;

    return `
        <tr>
            <td style="padding:16px 8px;">
                <span style="background:#f1f5f9; padding:8px 12px; border-radius:999px; font-weight:600;">
                    ${r.intent}
                </span>
            </td>

            <td style="padding:16px 8px; min-width:250px;">${exHtml}</td>

            <td style="padding:16px 8px;">${entHtml}</td>

            <td style="padding:16px 8px;">${statusHtml}</td>

            <td style="padding:16px 8px; color:#64748b;">${r.date_added}</td>

            <td style="padding:16px 8px;">
                <button onclick="deleteRow(${r.id})" class="delete-btn">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </td>
        </tr>
    `;
}



// ---------- LOAD ALL TRAINING DATA ----------
async function loadTrainingData() {
    const res = await fetch("/get_training_data");
    const j = await res.json();
    const rows = j.data;

    document.getElementById("trainingTbody").innerHTML =
        rows.map(r => renderRow(r)).join("");

    const pending = rows.filter(r => r.status === "pending").length;
    const pendingCountElem = document.getElementById("pendingCount");
    if (pendingCountElem) pendingCountElem.textContent = pending;
}



// ======================== MODAL FUNCTIONS ========================
function openAddModal() {
    document.getElementById("addModal").style.display = "flex";
}

function closeAddModal() {
    document.getElementById("addModal").style.display = "none";
}

// ======================== ADD FROM USER QUERY ========================
function openAddFromQuery(queryText) {

    // open modal
    document.getElementById("addModal").style.display = "flex";

    // pre-fill the examples area with the user query
    document.getElementById("modalExamples").value = queryText;

    // clear intent (admin must select/enter)
    document.getElementById("modalIntent").value = "";

    // clear entities
    document.getElementById("modalEntities").value = "";
}

// ======================== ADD NEW TRAINING DATA ========================
async function submitAddModal() {
    let intent = document.getElementById("modalIntent").value.trim();
    let examples = document.getElementById("modalExamples").value.trim();
    let entities = document.getElementById("modalEntities").value.trim();

    if (!intent || !examples) {
        alert("Intent and at least one example are required.");
        return;
    }

    let formData = new URLSearchParams();
    formData.append("intent", intent);
    formData.append("examples", examples);
    formData.append("entities", entities);

    const res = await fetch("/add_training_data", {
        method: "POST",
        body: formData,
    });

    if (res.ok) {
        closeAddModal();
        await loadTrainingData();
        alert("Training data added successfully!");
    }
}



// ======================== DELETE TRAINING DATA ========================
async function deleteRow(id) {
    if (!confirm("Delete this training row?")) return;

    const res = await fetch(`/delete_training_data/${id}`, { method: "POST" });

    if (res.ok) await loadTrainingData();
}



// ======================== TRAIN MODEL ========================
async function startTraining() {
    if (!confirm("Train all pending items?")) return;

    document.getElementById("trainBtn").disabled = true;

    const res = await fetch("/train_model", { method: "POST" });
    const j = await res.json();

    if (j.status === "trained") {
        alert(`Training completed. ${j.count} items added to CSV.`);
    } else {
        alert("No pending items to train.");
    }

    await loadTrainingData();
    document.getElementById("trainBtn").disabled = false;
}



// =============================================================
//                 USER QUERIES MODULE
// =============================================================

// ---------- RENDER ONE USER QUERY ROW ----------
function renderUserQueryRow(q) {

    let confClass =
        q.confidence < 30 ? "conf-red" :
        q.confidence < 50 ? "conf-yellow" :
        "conf-green";

    let reasonHtml = "";
    if (q.reason === "irrelevant")
        reasonHtml = `<span class="reason-badge reason-irrelevant">Irrelevant</span>`;
    else if (q.reason === "fallback")
        reasonHtml = `<span class="reason-badge reason-fallback">Fallback</span>`;
    else if (q.reason === "low_confidence")
        reasonHtml = `<span class="reason-badge reason-low">Low Confidence</span>`;

    let intentHtml = q.intent
        ? `<span class="intent-badge">${q.intent}</span>`
        : "-";

    return `
        <tr>
            <td>${q.query}</td>
            <td>${intentHtml}</td>
            <td class="${confClass}">${q.confidence}%</td>
            <td>${reasonHtml}</td>
            <td>${q.time}</td>
            <td>
                <button class="add-btn" onclick="openAddFromQuery('${q.query.replace(/'/g, "\\'")}')">
                    Add to Training
                </button>
            </td>
        </tr>
    `;
}

// ---------- LOAD USER QUERIES ----------
async function loadUserQueries() {
    const res = await fetch("/get_unanswered_queries");
    const data = await res.json();

    document.getElementById("userQueriesTbody").innerHTML =
        data.rows.map(r => renderUserQueryRow(r)).join("");

    // 🟠 COUNT CALCULATIONS
    let fallback = 0, low = 0, irre = 0;

    data.rows.forEach(r => {
        if (r.reason === "fallback") fallback++;
        else if (r.reason === "low_confidence") low++;
        else if (r.reason === "irrelevant") irre++;
    });

    // 🟣 UPDATE UI
    document.getElementById("fallbackCount").textContent = fallback;
    document.getElementById("lowCount").textContent = low;
    document.getElementById("irrelevantCount").textContent = irre;

    // TOTAL UNRESOLVED
    document.getElementById("totalUnresolved").textContent =
        fallback + low + irre;
}

// =================== FAQ MODAL ===================
function openFaqModal() {
    document.getElementById("faqModal").style.display = "flex";
}

function closeFaqModal() {
    document.getElementById("faqModal").style.display = "none";
}

// Show/hide custom category box
function toggleOtherCategory() {
    const cat = document.getElementById("faqCategory").value;
    document.getElementById("otherCategoryBox").style.display =
        (cat === "Other") ? "block" : "none";
}

async function submitFaq() {
    let q = document.getElementById("faqQuestion").value.trim();
    let a = document.getElementById("faqAnswer").value.trim();
    let cat = document.getElementById("faqCategory").value;
    let other = document.getElementById("faqOtherCategory").value.trim();

    if (!q || !a) {
        alert("Question and answer are required.");
        return;
    }

    // handle custom category
    if (cat === "Other") {
        if (!other) {
            alert("Please enter the category.");
            return;
        }
        cat = other;
    }

    let formData = new URLSearchParams();
    formData.append("question", q);
    formData.append("answer", a);
    formData.append("category", cat);

    // 🔥 CHECK IF WE ARE EDITING
    if (window.editFaqId) {
        formData.append("id", window.editFaqId);

        const res = await fetch("/update_faq", {
            method: "POST",
            body: formData
        });

        const j = await res.json();

        if (j.status === "success") {
            alert("FAQ updated successfully!");
            window.editFaqId = null; // reset flag
            closeFaqModal();
            loadFaqs();
            return;
        }
    }

    // 🔥 OTHERWISE ADD NEW FAQ
    const res = await fetch("/add_faq", {
        method: "POST",
        body: formData
    });

    const j = await res.json();

    if (j.status === "success") {
        alert("FAQ added successfully!");
        closeFaqModal();
        loadFaqs();
    }
}

// ======================== LOAD FAQS ========================
async function loadFaqs() {
    const res = await fetch("/get_faqs");
    const data = await res.json();

    let html = "";

    data.faqs.forEach(f => {
        html += `
            <div class="faq-card">
                
                <!-- TOP ROW: QUESTION + ARROW -->
                <div class="faq-top" onclick="toggleFaq(this)">
                    <div class="faq-question">${f.question}</div>

                    <i class="fa-solid fa-chevron-down faq-arrow"></i>
                </div>

                <!-- HIDDEN CONTENT -->
                <div class="faq-content">
                    <div class="faq-answer-label">Answer</div>
                    <div class="faq-answer">${f.answer}</div>

                    <div class="faq-actions">
                        <button class="faq-edit" onclick="editFaq(${f.id})">Edit</button>
                        <button class="faq-delete" onclick="deleteFaq(${f.id})">Delete</button>
                    </div>
                </div>
            </div>
        `;
    });

    document.getElementById("faqList").innerHTML = html;
}

function toggleFaq(el) {
    const card = el.parentElement;
    const content = card.querySelector(".faq-content");
    const arrow = card.querySelector(".faq-arrow");

    content.classList.toggle("open");

    // rotate arrow
    if (content.classList.contains("open")) {
        arrow.classList.remove("fa-chevron-down");
        arrow.classList.add("fa-chevron-up");
        arrow.style.color = "#ff7b00";   // orange
    } else {
        arrow.classList.remove("fa-chevron-up");
        arrow.classList.add("fa-chevron-down");
        arrow.style.color = "#b45309";   // darker orange
    }
}

async function deleteFaq(id) {
    if (!confirm("Are you sure you want to delete this FAQ?")) return;

    const res = await fetch(`/delete_faq/${id}`, { method: "POST" });
    const data = await res.json();

    if (data.status === "success") {
        loadFaqs();
        alert("FAQ deleted successfully!");
    }
}

async function editFaq(id) {
    const res = await fetch(`/get_faq/${id}`);
    const data = await res.json();

    if (!data.faq) {
        alert("FAQ not found!");
        return;
    }

    // Open modal
    openFaqModal();

    // Fill existing data
    document.getElementById("faqQuestion").value = data.faq.question;
    document.getElementById("faqAnswer").value = data.faq.answer;

    // store ID for update
    window.editFaqId = id;
}

async function loadAnalytics() {
    const res = await fetch("/get_analytics");
    const data = await res.json();

    // ---------------- TOP METRICS ----------------
    document.getElementById("totalChats").textContent = data.total_chats;
    document.getElementById("avgConfidence").textContent = data.avg_confidence + "%";
    document.getElementById("avgResponse").textContent = data.avg_response + "s";
    document.getElementById("userRating").textContent = data.user_rating + "/5";

    // ---------------- INTENT PERFORMANCE ----------------
    document.getElementById("intentPerformanceBody").innerHTML =
        data.intent_performance.map(i => `
            <tr>
                <td><span class="intent-tag">${i.intent}</span></td>
                <td>${i.total_queries}</td>
                <td style="font-weight:600;">${i.accuracy}%</td>
            </tr>
        `).join("");

    // ---------------- ENTITY PERFORMANCE ----------------
    document.getElementById("entityPerformanceBody").innerHTML =
        data.entities.map(e => `
            <tr>
            <td><span class="intent-tag">${e.entity}</span></td>
            <td>${e.detected}</td>
            <td style="font-weight:600;">${e.accuracy}%</td>
            </tr>
    `).join("");
    
    // ---------------- TOP QUERIES ----------------
    document.getElementById("topQueriesBody").innerHTML =
        data.top_queries.map((q, i) => `
            <tr>
                <td>${i + 1}</td>
                <td>${q.question}</td>
                <td style="text-align:right;">${q.count}</td>
            </tr>
        `).join("");

    // ---------------- CHARTS ----------------
    renderIntentChart(data.intent_chart);
    renderConfidenceChart(data.confidence_chart);
    renderVolumeChart(data.volume_chart);
}

function exportAnalyticsCSV() {
    window.location = "/export_analytics_csv";
}

function loadCharts() {

    // ---- Intent distribution ----
    new Chart(document.getElementById("intentChart"), {
        type: "pie",
        data: {
            labels: analytics_intents.map(i => i.intent),
            datasets: [{
                data: analytics_intents.map(i => i.count),
                backgroundColor: ["#0b71d9", "#22c55e", "#8a3ffc", "#ff7b00", "#dc2626"]
            }]
        }
    });

    // ---- Confidence trend ----
    new Chart(document.getElementById("confidenceChart"), {
        type: "line",
        data: {
            labels: analytics_conf.map(c => c.date),
            datasets: [{
                label: "Avg Confidence (%)",
                data: analytics_conf.map(c => c.value),
                borderColor: "#0b71d9",
                borderWidth: 3,
                tension: 0.4
            }]
        }
    });

    // ---- Daily Query Volume ----
    new Chart(document.getElementById("volumeChart"), {
        type: "bar",
        data: {
            labels: analytics_volume.map(v => v.date),
            datasets: [{
                label: "Queries",
                data: analytics_volume.map(v => v.count),
                backgroundColor: "#8a3ffc"
            }]
        }
    });
}

function renderIntentChart(info) {

    const colors = [
        "#0b71d9", "#8a3ffc", "#ff7b00", "#22c55e", "#ec4899",
        "#14b8a6", "#f43f5e", "#a855f7", "#f59e0b", "#10b981",
        "#3b82f6", "#ef4444", "#6366f1", "#84cc16", "#f97316",
        "#06b6d4", "#d946ef", "#475569", "#64748b", "#4ade80"
    ];

    // If intents > 20, repeat colors safely
    const finalColors = info.labels.map((_, i) => colors[i % colors.length]);

    new Chart(document.getElementById("intentChart"), {
        type: "pie",
        data: {
            labels: info.labels,
            datasets: [{
                data: info.values,
                backgroundColor: finalColors,
                borderWidth: 1,
                borderColor: "#fff"
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: "bottom",
                    labels: {
                        font: { size: 13 },
                        padding: 12
                    }
                }
            }
        }
    });
}

function renderConfidenceChart(info) {
    new Chart(document.getElementById("confidenceChart"), {
        type: "line",
        data: {
            labels: info.labels,
            datasets: [{
                label: "Avg Confidence %",
                data: info.values,
                borderWidth: 2
            }]
        }
    });
}

function renderVolumeChart(info) {
    new Chart(document.getElementById("volumeChart"), {
        type: "bar",
        data: {
            labels: info.labels,
            datasets: [{
                label: "Queries",
                data: info.values,
                borderWidth: 1
            }]
        }
    });
}

async function saveProfile() {
    let name = document.getElementById("profileName").value.trim();
    let email = document.getElementById("profileEmail").value.trim();

    if (!name || !email) {
        alert("Name and Email cannot be empty!");
        return;
    }

    let form = new URLSearchParams();
    form.append("name", name);
    form.append("email", email);

    const res = await fetch("/update_admin_profile", {
        method: "POST",
        body: form
    });

    const data = await res.json();

    if (data.status === "success") {
        alert("✔ Profile updated successfully!");
        location.reload();  // reload to update displayed values
    }
}

async function resetPassword() {
    const res = await fetch("/reset_admin_password", {
        method: "POST"
    });

    const data = await res.json();
    alert(data.message);
}


function exportTrainingData() {
    window.location = "/export_analytics_csv"; 
}

function openHelp() {
    window.open("https://your-help-link.com", "_blank");
}

function logoutAdmin() {
    window.location = "/login";
}

// ================= DARK MODE TOGGLE =================
const darkToggle = document.getElementById("darkModeToggle");

// Load(saved theme)
if (localStorage.getItem("dark-mode") === "enabled") {
    document.body.classList.add("dark");
    darkToggle.checked = true;
}

// Toggle theme
darkToggle.addEventListener("change", () => {
    if (darkToggle.checked) {
        document.body.classList.add("dark");
        localStorage.setItem("dark-mode", "enabled");
    } else {
        document.body.classList.remove("dark");
        localStorage.setItem("dark-mode", "disabled");
    }
});

document.getElementById("emailNotifyToggle").addEventListener("change", async function() {
    const enabled = this.checked;

    await fetch("/update_email_notifications", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ enabled })
    });

    alert("Email notifications " + (enabled ? "enabled" : "disabled"));
});
