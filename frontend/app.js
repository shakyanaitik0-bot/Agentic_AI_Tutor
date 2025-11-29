// API Configuration
const API_BASE_URL = 'http://127.0.0.1:8000/api';

// Application State
const state = {
    studentId: null,
    sessionId: null,
    studentData: null,
    currentQuiz: null
};

// DOM Elements
const elements = {
    // Sections
    registrationSection: document.getElementById('registration-section'),
    dashboardSection: document.getElementById('dashboard-section'),
    loadingOverlay: document.getElementById('loading-overlay'),

    // Forms and Inputs
    registrationForm: document.getElementById('registration-form'),
    chatInput: document.getElementById('chat-input'),
    chatMessages: document.getElementById('chat-messages'),

    // Buttons
    btnSendMessage: document.getElementById('btn-send-message'),
    btnStartSession: document.getElementById('btn-start-session'),
    btnEndSession: document.getElementById('btn-end-session'),
    btnViewProgress: document.getElementById('btn-view-progress'),
    btnGeneratePlan: document.getElementById('btn-generate-plan'),

    // Display elements
    displayName: document.getElementById('display-name'),
    displayExam: document.getElementById('display-exam'),
    sessionStatus: document.getElementById('session-status'),
    quizContainer: document.getElementById('quiz-container'),
    progressContainer: document.getElementById('progress-container'),
    planContainer: document.getElementById('plan-container'),

    // Tab navigation
    tabNavigation: document.getElementById('tab-navigation'),
    tabContent: document.getElementById('tab-content'),
    tabButtons: document.querySelectorAll('.tab-btn'),
    tabs: {
        chat: document.getElementById('tab-chat'),
        quiz: document.getElementById('tab-quiz'),
        progress: document.getElementById('tab-progress'),
        plan: document.getElementById('tab-plan')
    }
};

// Utility Functions
function showLoading() {
    elements.loadingOverlay.classList.remove('hidden');
}

function hideLoading() {
    elements.loadingOverlay.classList.add('hidden');
}

// Tab switching
function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        }
    });

    // Update tab content
    Object.keys(elements.tabs).forEach(key => {
        elements.tabs[key].classList.remove('active');
    });
    elements.tabs[tabName].classList.add('active');
}

// Initialize tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        switchTab(btn.dataset.tab);
    });
});

function addChatMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;

    const strongTag = document.createElement('strong');
    strongTag.textContent = role === 'user' ? 'You:' : 'AI Tutor:';

    messageDiv.appendChild(strongTag);

    if (typeof content === 'string') {
        messageDiv.innerHTML += ' ' + content;
    } else {
        messageDiv.appendChild(content);
    }

    elements.chatMessages.appendChild(messageDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

// API Functions
async function apiRequest(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Request failed');
        }

        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// Registration (removed weak/strong areas - system discovers these automatically)
elements.registrationForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    showLoading();

    try {
        const formData = {
            name: document.getElementById('student-name').value,
            email: document.getElementById('student-email').value,
            exam_type: document.getElementById('exam-type').value,
            weak_areas: [],  // Will be discovered through quizzes
            strong_areas: [], // Will be discovered through quizzes
            learning_preferences: {
                style: 'adaptive',
                practice_intensity: 'medium'
            }
        };

        const data = await apiRequest('/students/register', {
            method: 'POST',
            body: JSON.stringify(formData)
        });

        state.studentId = data.id;
        state.studentData = data;

        // Update dashboard
        elements.displayName.textContent = data.name;
        elements.displayExam.textContent = data.exam_type;

        // Show dashboard
        elements.registrationSection.classList.add('hidden');
        elements.dashboardSection.classList.remove('hidden');

        hideLoading();
    } catch (error) {
        hideLoading();
        alert('Registration failed: ' + error.message);
    }
});

// Start Session
elements.btnStartSession.addEventListener('click', async () => {
    showLoading();

    try {
        const data = await apiRequest('/sessions/start', {
            method: 'POST',
            body: JSON.stringify({
                student_id: state.studentId,
                session_type: 'general'
            })
        });

        state.sessionId = data.id;
        elements.sessionStatus.textContent = 'Active ✓';
        elements.btnStartSession.classList.add('hidden');
        elements.btnEndSession.classList.remove('hidden');

        // Enable buttons
        elements.chatInput.disabled = false;
        elements.btnSendMessage.disabled = false;
        elements.btnViewProgress.disabled = false;
        elements.btnGeneratePlan.disabled = false;

        // Show tabs
        elements.tabNavigation.classList.remove('hidden');
        elements.tabContent.classList.remove('hidden');

        // Switch to chat tab
        switchTab('chat');

        hideLoading();
    } catch (error) {
        hideLoading();
        alert('Failed to start session: ' + error.message);
    }
});

// End Session
elements.btnEndSession.addEventListener('click', async () => {
    if (!confirm('Are you sure you want to end this session?')) {
        return;
    }

    showLoading();

    try {
        await apiRequest(`/sessions/${state.sessionId}/end`, {
            method: 'POST'
        });

        state.sessionId = null;
        elements.sessionStatus.textContent = 'Ended';
        elements.btnStartSession.classList.remove('hidden');
        elements.btnEndSession.classList.add('hidden');

        // Disable chat
        elements.chatInput.disabled = true;
        elements.btnSendMessage.disabled = true;

        hideLoading();
        alert('Session ended successfully!');
    } catch (error) {
        hideLoading();
        alert('Failed to end session: ' + error.message);
    }
});

// Send Chat Message
async function sendMessage() {
    const message = elements.chatInput.value.trim();
    if (!message || !state.sessionId) return;

    // Add user message to chat
    addChatMessage('user', message);
    elements.chatInput.value = '';

    showLoading();

    try {
        const data = await apiRequest('/chat', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                message: message,
                intent: null
            })
        });

        hideLoading();

        // Handle response based on agent type
        const response = data.agent_response;

        if (response.quiz) {
            // Display quiz
            displayQuiz(response.quiz);
        } else if (response.plan) {
            // Display study plan
            displayStudyPlan(response.plan);
        } else if (response.feedback) {
            // Display feedback
            displayFeedback(response.feedback);
        } else if (response.response) {
            // Regular conversation
            addChatMessage('assistant', response.response);
        } else {
            addChatMessage('assistant', 'Response received. Check the dashboard for details.');
        }

    } catch (error) {
        hideLoading();
        addChatMessage('assistant', `Error: ${error.message}`);
    }
}

elements.btnSendMessage.addEventListener('click', sendMessage);
elements.chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// Display Quiz
function displayQuiz(quiz) {
    state.currentQuiz = quiz;

    let html = `
        <div class="quiz-info">
            <h3>Quiz: ${quiz.topic}</h3>
            <p>Difficulty: <strong>${quiz.difficulty}</strong> | Questions: ${quiz.num_questions}</p>
            <p class="info-text">Your performance on this quiz will help me understand your strengths and areas for improvement.</p>
        </div>
    `;

    quiz.questions.forEach((q, index) => {
        html += `
            <div class="quiz-question">
                <h3>Question ${index + 1}</h3>
                <p>${q.question_text}</p>
                ${q.options.map((option, optIndex) => `
                    <label class="quiz-option">
                        <input type="radio" name="q${index}" value="${optIndex}">
                        ${option}
                    </label>
                `).join('')}
            </div>
        `;
    });

    html += '<button class="btn btn-primary" onclick="submitQuiz()">Submit Quiz</button>';

    elements.quizContainer.innerHTML = html;

    // Switch to quiz tab
    switchTab('quiz');

    addChatMessage('assistant', 'Quiz generated! Switch to the Quiz tab to answer the questions.');
}

// Submit Quiz
async function submitQuiz() {
    if (!state.currentQuiz) return;

    const answers = [];
    for (let i = 0; i < state.currentQuiz.num_questions; i++) {
        const selected = document.querySelector(`input[name="q${i}"]:checked`);
        if (!selected) {
            alert(`Please answer question ${i + 1}`);
            return;
        }
        answers.push(parseInt(selected.value));
    }

    showLoading();

    try {
        const data = await apiRequest('/quiz/submit', {
            method: 'POST',
            body: JSON.stringify({
                quiz_id: state.currentQuiz.quiz_id,
                student_id: state.studentId,
                answers: answers
            })
        });

        hideLoading();

        const resultClass = data.passed ? 'passed' : 'failed';
        const resultHTML = `
            <div class="quiz-result ${resultClass}">
                <h3>Quiz Results</h3>
                <p>Score: ${data.correct_answers}/${data.total_questions} (${data.accuracy.toFixed(1)}%)</p>
                <p>Status: ${data.passed ? 'Passed ✓' : 'Failed ✗'}</p>
            </div>
        `;

        elements.quizContainer.innerHTML += resultHTML;
        addChatMessage('assistant', `Quiz completed! Score: ${data.accuracy.toFixed(1)}%`);

    } catch (error) {
        hideLoading();
        alert('Failed to submit quiz: ' + error.message);
    }
}

// View Progress
elements.btnViewProgress.addEventListener('click', async () => {
    showLoading();

    try {
        const data = await apiRequest(`/feedback/${state.studentId}`);
        hideLoading();
        displayFeedback(data);
    } catch (error) {
        hideLoading();
        alert('Failed to load progress: ' + error.message);
    }
});

// Display Feedback
function displayFeedback(feedback) {
    const stats = feedback.overall_stats;

    let html = `
        <h3>Overall Performance</h3>
        <div class="stats-grid">
            <div class="stat-card">
                <h4>Overall Accuracy</h4>
                <div class="value">${stats.overall_accuracy.toFixed(1)}%</div>
            </div>
            <div class="stat-card">
                <h4>Total Attempts</h4>
                <div class="value">${stats.total_attempts}</div>
            </div>
            <div class="stat-card">
                <h4>Weak Topics</h4>
                <div class="value">${stats.weak_topics_count}</div>
            </div>
            <div class="stat-card">
                <h4>Strong Topics</h4>
                <div class="value">${stats.strong_topics_count}</div>
            </div>
        </div>
    `;

    if (feedback.weak_topics.length > 0) {
        html += '<h3>Weak Topics (Need Practice)</h3><div class="topic-list">';
        feedback.weak_topics.forEach(topic => {
            html += `
                <div class="topic-item weak">
                    <h4>${topic.topic}</h4>
                    <p>Accuracy: ${topic.accuracy.toFixed(1)}% | Attempts: ${topic.attempts}</p>
                    <p><em>System automatically identified this as a weak area based on your performance</em></p>
                </div>
            `;
        });
        html += '</div>';
    }

    if (feedback.strong_topics.length > 0) {
        html += '<h3>Strong Topics</h3><div class="topic-list">';
        feedback.strong_topics.forEach(topic => {
            html += `
                <div class="topic-item strong">
                    <h4>${topic.topic}</h4>
                    <p>Accuracy: ${topic.accuracy.toFixed(1)}% | Attempts: ${topic.attempts}</p>
                </div>
            `;
        });
        html += '</div>';
    }

    if (feedback.recommendations.length > 0) {
        html += '<h3>AI-Generated Recommendations</h3><ul>';
        feedback.recommendations.forEach(rec => {
            html += `<li>${rec}</li>`;
        });
        html += '</ul>';
    }

    elements.progressContainer.innerHTML = html;

    // Switch to progress tab
    switchTab('progress');
}

// Generate Study Plan
elements.btnGeneratePlan.addEventListener('click', async () => {
    const days = prompt('Enter study plan duration (days):', '30');
    if (!days || isNaN(days)) return;

    const hours = prompt('Study hours per day:', '4');
    if (!hours || isNaN(hours)) return;

    showLoading();

    try {
        const data = await apiRequest('/plan/generate', {
            method: 'POST',
            body: JSON.stringify({
                student_id: state.studentId,
                timeline_days: parseInt(days),
                hours_per_day: parseFloat(hours),
                focus_topics: state.studentData.weak_areas
            })
        });

        hideLoading();
        displayStudyPlan(data);
    } catch (error) {
        hideLoading();
        alert('Failed to generate plan: ' + error.message);
    }
});

// Display Study Plan
function displayStudyPlan(plan) {
    let html = `
        <div class="plan-overview">
            <h3>Adaptive Study Plan</h3>
            <p><strong>Duration:</strong> ${plan.timeline_days} days</p>
            <p><strong>Total Topics:</strong> ${plan.total_topics}</p>
            <p><strong>Estimated Hours:</strong> ${plan.total_estimated_hours}</p>
            <p class="info-text">This plan is based on your current performance and adapts to your learning pace. Focus areas are prioritized based on your weak topics.</p>
            <p>${plan.explanation}</p>
        </div>
    `;

    if (plan.topics && plan.topics.length > 0) {
        html += '<h3>Topics to Cover (Prioritized)</h3><div class="topic-list">';
        plan.topics.forEach(topic => {
            html += `
                <div class="topic-item">
                    <h4>${topic.topic} (Priority ${topic.priority})</h4>
                    <p>Urgency: <strong>${topic.urgency}</strong> | Estimated Hours: ${topic.estimated_hours}</p>
                    <p><em>Why: ${topic.reason}</em></p>
                </div>
            `;
        });
        html += '</div>';
    }

    if (plan.daily_schedule && plan.daily_schedule.length > 0) {
        html += '<h3>Daily Schedule (First 7 Days)</h3><div class="daily-schedule">';
        plan.daily_schedule.slice(0, 7).forEach(day => {
            html += `
                <div class="day-card">
                    <h4>Day ${day.day}</h4>
                    <p>Study Hours: ${day.hours_allocated}</p>
                    <ul>
                        ${day.topics.map(t => `<li>${t}</li>`).join('')}
                    </ul>
                </div>
            `;
        });
        html += '</div>';
    }

    elements.planContainer.innerHTML = html;

    // Switch to plan tab
    switchTab('plan');
}

// Make submitQuiz available globally
window.submitQuiz = submitQuiz;

// Initialize
console.log('Agentic AI Tutor initialized');
