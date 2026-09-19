// API Configuration
const API_BASE_URL = 'http://127.0.0.1:8000/api';

// Application State
const state = {
    studentId: null,
    sessionId: null,
    studentData: null,
    currentQuiz: null,
    accessToken: null,
    refreshToken: null,
    // Flashcard state
    flashcardDecks: [],
    currentStudySession: null,
    currentCardIndex: 0,
    studyStartTime: null
};

// Auth token handling. The API rejects any data request without a valid
// access token, so every call below must go through authHeaders().
const TOKEN_STORAGE_KEY = 'tutorAuthTokens';

function storeTokens(tokens) {
    state.accessToken = tokens.access_token;
    state.refreshToken = tokens.refresh_token;

    try {
        sessionStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify({
            access_token: tokens.access_token,
            refresh_token: tokens.refresh_token
        }));
    } catch (e) {
        // sessionStorage can be unavailable (private mode); tokens still work
        // for this page load.
        console.warn('Could not persist tokens:', e);
    }
}

function clearTokens() {
    state.accessToken = null;
    state.refreshToken = null;

    try {
        sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    } catch (e) {
        console.warn('Could not clear tokens:', e);
    }
}

function authHeaders(extra = {}) {
    if (!state.accessToken) {
        return { ...extra };
    }
    return { ...extra, Authorization: `Bearer ${state.accessToken}` };
}

// Exchange the refresh token for a new pair. Returns true on success.
async function refreshSession() {
    if (!state.refreshToken) {
        return false;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/students/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: state.refreshToken })
        });

        if (!response.ok) {
            return false;
        }

        storeTokens(await response.json());
        return true;
    } catch (error) {
        console.error('Token refresh failed:', error);
        return false;
    }
}

// Send the user back to the login screen when their session can no longer be
// renewed.
function handleSessionExpired() {
    clearTokens();
    state.studentId = null;
    state.sessionId = null;
    state.studentData = null;

    elements.dashboardSection.classList.add('hidden');
    elements.registrationSection.classList.remove('hidden');
    alert('Your session has expired. Please log in again.');
}

// fetch() wrapper that attaches the access token and retries once after
// refreshing an expired one.
async function authFetch(url, options = {}) {
    const send = () => fetch(url, {
        ...options,
        headers: authHeaders(options.headers || {})
    });

    let response = await send();

    if (response.status === 401 && await refreshSession()) {
        response = await send();
    }

    if (response.status === 401) {
        handleSessionExpired();
    }

    return response;
}

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
        flashcards: document.getElementById('tab-flashcards'),
        progress: document.getElementById('tab-progress'),
        plan: document.getElementById('tab-plan'),
        documents: document.getElementById('tab-documents')
    },

    // Flashcard elements
    flashcardGenerateForm: document.getElementById('flashcard-generate-form'),
    flashcardDecks: document.getElementById('flashcard-decks'),
    flashcardStudyArea: document.getElementById('flashcard-study-area'),
    flashcardCardDisplay: document.getElementById('flashcard-card-display'),
    flashcardStats: document.getElementById('flashcard-stats'),

    // Document elements
    documentUploadForm: document.getElementById('document-upload-form'),
    documentsList: document.getElementById('documents-list'),
    uploadStatus: document.getElementById('upload-status')
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
        const response = await authFetch(`${API_BASE_URL}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
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

// Toggle between login and registration forms
document.getElementById('link-register').addEventListener('click', (e) => {
    e.preventDefault();
    document.getElementById('login-step').classList.add('hidden');
    elements.registrationForm.classList.remove('hidden');
});

document.getElementById('link-login').addEventListener('click', (e) => {
    e.preventDefault();
    elements.registrationForm.classList.add('hidden');
    document.getElementById('login-step').classList.remove('hidden');
});

// Login Handler
document.getElementById('btn-login').addEventListener('click', async () => {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    if (!email || !password) {
        alert('Please enter both email and password');
        return;
    }

    showLoading();

    try {
        const data = await apiRequest('/students/login', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });

        // Login successful - keep the tokens before any authenticated call
        storeTokens(data);
        state.studentId = data.id;
        state.studentData = data;

        // Update dashboard
        elements.displayName.textContent = data.name;
        elements.displayExam.textContent = data.exam_type;

        // Load previous session if exists
        await loadPreviousSession();

        // Load user's documents
        await initializeDocuments();

        // Load user's flashcard decks
        await initializeFlashcards();

        // Show dashboard
        elements.registrationSection.classList.add('hidden');
        elements.dashboardSection.classList.remove('hidden');

        hideLoading();
    } catch (error) {
        hideLoading();
        alert('Login failed: ' + error.message);
    }
});

// Registration Handler
elements.registrationForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    showLoading();

    try {
        const formData = {
            name: document.getElementById('student-name').value,
            email: document.getElementById('student-email').value,
            password: document.getElementById('student-password').value,
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

        // Registration signs the student in straight away
        storeTokens(data);
        state.studentId = data.id;
        state.studentData = data;

        // Update dashboard
        elements.displayName.textContent = data.name;
        elements.displayExam.textContent = data.exam_type;

        // Load user's documents (will be empty for new users)
        await initializeDocuments();

        // Load user's flashcard decks (will be empty for new users)
        await initializeFlashcards();

        // Show dashboard
        elements.registrationSection.classList.add('hidden');
        elements.dashboardSection.classList.remove('hidden');

        hideLoading();
    } catch (error) {
        hideLoading();
        alert('Registration failed: ' + error.message);
    }
});

// Load Previous Session (if exists)
async function loadPreviousSession() {
    try {
        // Get student's most recent active session
        const response = await authFetch(`${API_BASE_URL}/sessions?student_id=${state.studentId}`);

        if (!response.ok) {
            // No previous sessions - that's fine for new users
            return;
        }

        const sessions = await response.json();

        if (sessions && sessions.length > 0) {
            // Get the most recent session
            const lastSession = sessions[0];

            if (lastSession.is_active) {
                // Resume active session
                state.sessionId = lastSession.id;
                elements.sessionStatus.textContent = 'Active ✓';
                elements.btnStartSession.classList.add('hidden');
                elements.btnEndSession.classList.remove('hidden');

                // Enable features
                elements.chatInput.disabled = false;
                elements.btnSendMessage.disabled = false;
                elements.btnViewProgress.disabled = false;
                elements.btnGeneratePlan.disabled = false;

                // Show tabs
                elements.tabNavigation.classList.remove('hidden');
                elements.tabContent.classList.remove('hidden');

                // Load chat messages
                await loadSessionMessages(lastSession.id);

                addChatMessage('assistant', 'Welcome back! Your previous session has been restored.');
            }
        }
    } catch (error) {
        console.log('No previous session to load:', error);
        // Not a critical error - user can start a new session
    }
}

// Load Session Messages
async function loadSessionMessages(sessionId) {
    try {
        const response = await authFetch(`${API_BASE_URL}/sessions/${sessionId}/messages`);

        if (!response.ok) {
            return;
        }

        const messages = await response.json();

        // Clear existing messages (except welcome message)
        elements.chatMessages.innerHTML = '';

        // Add welcome message
        addChatMessage('assistant', 'Previous conversation restored:');

        // Load all messages and parse agent responses
        messages.forEach(msg => {
            if (msg.role === 'user') {
                // User messages are always plain text
                addChatMessage(msg.role, msg.content);
            } else if (msg.role === 'assistant') {
                // Use structured metadata if available, otherwise try parsing content
                const agentData = msg.message_metadata || null;

                if (agentData) {
                    // We have structured data - use it
                    if (agentData.quiz) {
                        displayQuiz(agentData.quiz);
                        addChatMessage('assistant', `[Quiz: ${agentData.quiz.topic}]`);
                    }
                    else if (agentData.study_plan || agentData.plan) {
                        const planData = agentData.study_plan || agentData.plan;
                        displayStudyPlan(planData);
                        addChatMessage('assistant', `[Study Plan: ${planData.timeline_days} days]`);
                    }
                    else if (agentData.data || agentData.feedback) {
                        const feedbackData = agentData.data || agentData.feedback;
                        displayFeedback(feedbackData);
                        addChatMessage('assistant', '[Progress Feedback Generated]');
                    }
                    else if (agentData.response) {
                        addChatMessage('assistant', agentData.response);
                    }
                    else {
                        // Unknown structure in metadata
                        addChatMessage('assistant', msg.content);
                    }
                } else {
                    // No metadata - display content as plain text
                    // (older messages or simple text responses)
                    addChatMessage('assistant', msg.content);
                }
            }
        });

    } catch (error) {
        console.log('Could not load messages:', error);
    }
}

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
        } else if (response.study_plan || response.plan) {
            // Display study plan (handle both study_plan and plan keys)
            displayStudyPlan(response.study_plan || response.plan);
        } else if (response.data || response.feedback) {
            // Display feedback (handle both data and feedback keys)
            displayFeedback(response.data || response.feedback);
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
    // Store quiz with ID
    state.currentQuiz = {
        quiz_id: quiz.quiz_id,
        topic: quiz.topic,
        difficulty: quiz.difficulty,
        num_questions: quiz.num_questions,
        questions: quiz.questions
    };

    console.log('Quiz stored:', state.currentQuiz); // Debug

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
    if (!state.currentQuiz) {
        alert('No quiz loaded');
        return;
    }

    if (!state.currentQuiz.quiz_id) {
        alert('Quiz ID is missing. Please generate a new quiz.');
        console.error('Missing quiz_id:', state.currentQuiz);
        return;
    }

    const answers = [];
    for (let i = 0; i < state.currentQuiz.num_questions; i++) {
        const selected = document.querySelector(`input[name="q${i}"]:checked`);
        if (!selected) {
            alert(`Please answer question ${i + 1}`);
            return;
        }
        answers.push(parseInt(selected.value));
    }

    console.log('Submitting quiz:', {
        quiz_id: state.currentQuiz.quiz_id,
        student_id: state.studentId,
        answers: answers
    });

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
        let resultHTML = `
            <div class="quiz-result ${resultClass}">
                <h3>Quiz Results</h3>
                <p>Score: ${data.correct_answers}/${data.total_questions} (${data.accuracy.toFixed(1)}%)</p>
                <p>Status: ${data.passed ? 'Passed ✓' : 'Failed ✗'}</p>
                ${data.error ? `<p class="info-text">Note: ${data.error}</p>` : ''}
            </div>
        `;

        // Add per-question breakdown if available
        if (data.results && data.results.length > 0) {
            resultHTML += '<div class="quiz-breakdown"><h4>Question Breakdown:</h4>';
            data.results.forEach((result, idx) => {
                const icon = result.is_correct ? '✓' : '✗';
                const statusClass = result.is_correct ? 'correct' : 'incorrect';
                const question = state.currentQuiz.questions[idx];

                resultHTML += `
                    <div class="question-result ${statusClass}">
                        <p><strong>Question ${idx + 1}:</strong> ${icon} ${result.is_correct ? 'Correct' : 'Incorrect'}</p>
                        <p class="question-text">${question.question_text}</p>
                        <p><strong>Your answer:</strong> ${question.options[result.selected_answer]}</p>
                        ${!result.is_correct ? `<p><strong>Correct answer:</strong> ${question.options[result.correct_answer]}</p>` : ''}
                        <p class="explanation"><em>Explanation:</em> ${result.explanation}</p>
                    </div>
                `;
            });
            resultHTML += '</div>';
        }

        elements.quizContainer.innerHTML += resultHTML;
        addChatMessage('assistant', `Quiz completed! Score: ${data.accuracy.toFixed(1)}%`);

    } catch (error) {
        hideLoading();
        console.error('Quiz submission error:', error);
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

// Document Upload Handler
elements.documentUploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const fileInput = document.getElementById('document-file');
    const subjectInput = document.getElementById('document-subject');
    const file = fileInput.files[0];

    if (!file) {
        alert('Please select a file');
        return;
    }

    // Check file size (10MB limit)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
        alert('File too large. Maximum size is 10MB');
        return;
    }

    showLoading();

    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('student_id', state.studentId);
        if (subjectInput.value) {
            formData.append('subject', subjectInput.value);
        }

        // FormData sets its own Content-Type boundary, so only the
        // Authorization header is added here.
        const response = await authFetch(`${API_BASE_URL}/documents/upload`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Upload failed');
        }

        hideLoading();

        // Show success message
        elements.uploadStatus.innerHTML = `
            <div class="quiz-result passed">
                <h4>✓ Upload Successful!</h4>
                <p><strong>${data.filename}</strong> has been processed.</p>
                <p>${data.num_chunks} text chunks added to your knowledge base.</p>
                <p class="info-text">${data.message}</p>
            </div>
        `;
        elements.uploadStatus.classList.remove('hidden');

        // Clear form
        fileInput.value = '';
        subjectInput.value = '';

        // Refresh documents list
        await loadStudentDocuments();

        // Hide success message after 5 seconds
        setTimeout(() => {
            elements.uploadStatus.classList.add('hidden');
        }, 5000);

    } catch (error) {
        hideLoading();
        alert('Upload failed: ' + error.message);
    }
});

// Load Student Documents
async function loadStudentDocuments() {
    if (!state.studentId) return;

    try {
        const response = await authFetch(`${API_BASE_URL}/documents/list/${state.studentId}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load documents');
        }

        if (data.documents.length === 0) {
            elements.documentsList.innerHTML = `
                <div class="empty-state">
                    <p>No documents uploaded yet. Upload your first study material above!</p>
                </div>
            `;
            return;
        }

        // Display documents
        let html = '<div class="topic-list">';
        data.documents.forEach(doc => {
            html += `
                <div class="topic-item">
                    <h4>📄 ${doc.filename}</h4>
                    <p><strong>Subject:</strong> ${doc.subject}</p>
                    <p><strong>Chunks:</strong> ${doc.num_chunks} text segments</p>
                    <p style="font-size: 0.85em; color: #718096;">
                        Your quizzes and AI responses will now reference this document!
                    </p>
                </div>
            `;
        });
        html += '</div>';

        html += `<p class="info-text" style="margin-top: 20px;">
            <strong>Total:</strong> ${data.documents.length} document(s), ${data.total_chunks} text chunks
        </p>`;

        elements.documentsList.innerHTML = html;

    } catch (error) {
        console.error('Error loading documents:', error);
    }
}

// Load documents when user logs in
async function initializeDocuments() {
    await loadStudentDocuments();
}

// ==================== FLASHCARD FUNCTIONS ====================

// Generate Flashcards
elements.flashcardGenerateForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const topic = document.getElementById('flashcard-topic').value;
    const numCards = parseInt(document.getElementById('flashcard-count').value);
    const difficulty = document.getElementById('flashcard-difficulty').value;
    const useDocs = document.getElementById('flashcard-use-docs').checked;

    if (!topic) {
        alert('Please enter a topic');
        return;
    }

    showLoading();

    try {
        const data = await apiRequest(`/flashcards/generate/${state.studentId}`, {
            method: 'POST',
            body: JSON.stringify({
                topic: topic,
                num_cards: numCards,
                difficulty: difficulty,
                use_documents: useDocs
            })
        });

        hideLoading();

        // Refresh decks list
        await loadFlashcardDecks();

        // Show success message
        addChatMessage('assistant', `Created flashcard deck "${data.name}" with ${data.card_count} cards on ${data.topic}!`);

        // Clear form
        document.getElementById('flashcard-topic').value = '';

    } catch (error) {
        hideLoading();
        alert('Failed to generate flashcards: ' + error.message);
    }
});

// Load Flashcard Decks
async function loadFlashcardDecks() {
    if (!state.studentId) return;

    try {
        const decks = await apiRequest(`/flashcards/decks/${state.studentId}`);
        state.flashcardDecks = decks;

        if (decks.length === 0) {
            elements.flashcardDecks.innerHTML = `
                <div class="empty-state">
                    <p>No flashcard decks yet. Generate your first deck above!</p>
                </div>
            `;
            return;
        }

        let html = '<div class="topic-list">';
        decks.forEach(deck => {
            const masteryPercent = deck.card_count > 0
                ? Math.round((deck.mastered_count / deck.card_count) * 100)
                : 0;

            html += `
                <div class="topic-item flashcard-deck">
                    <h4>🎴 ${deck.name}</h4>
                    <p><strong>Topic:</strong> ${deck.topic}</p>
                    <p><strong>Cards:</strong> ${deck.card_count} total | ${deck.due_count} due | ${deck.new_count} new</p>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${masteryPercent}%"></div>
                    </div>
                    <p class="mastery-text">${masteryPercent}% mastered (${deck.mastered_count}/${deck.card_count})</p>
                    <div class="deck-actions">
                        <button class="btn btn-primary btn-sm" onclick="startStudySession('${deck.id}')">
                            📖 Study Now
                        </button>
                        <button class="btn btn-secondary btn-sm" onclick="deleteDeck('${deck.id}')">
                            🗑️ Delete
                        </button>
                    </div>
                </div>
            `;
        });
        html += '</div>';

        elements.flashcardDecks.innerHTML = html;

        // Also load stats
        await loadFlashcardStats();

    } catch (error) {
        console.error('Error loading flashcard decks:', error);
    }
}

// Start Study Session
async function startStudySession(deckId) {
    showLoading();

    try {
        const session = await apiRequest(`/flashcards/study/${deckId}?max_cards=20&include_new=true`);
        state.currentStudySession = session;
        state.currentCardIndex = 0;

        hideLoading();

        if (session.cards.length === 0) {
            alert('No cards due for review! Check back later.');
            return;
        }

        // Show study area
        elements.flashcardStudyArea.classList.remove('hidden');

        // Display first card
        displayCurrentCard();

    } catch (error) {
        hideLoading();
        alert('Failed to start study session: ' + error.message);
    }
}

// Display Current Flashcard
function displayCurrentCard() {
    const session = state.currentStudySession;
    if (!session || state.currentCardIndex >= session.cards.length) {
        // Session complete
        endStudySession();
        return;
    }

    const card = session.cards[state.currentCardIndex];
    state.studyStartTime = Date.now();

    let html = `
        <div class="flashcard-container">
            <div class="flashcard-progress">
                Card ${state.currentCardIndex + 1} of ${session.cards.length}
                | Due: ${session.total_due} | New: ${session.total_new}
            </div>

            <div class="flashcard" id="current-flashcard">
                <div class="flashcard-front">
                    <span class="card-type-badge ${card.type}">${card.type.toUpperCase()}</span>
                    <span class="card-difficulty-badge ${card.difficulty}">${card.difficulty}</span>
                    <div class="flashcard-content">
                        <p>${card.front}</p>
                    </div>
                    ${card.hints && card.hints.length > 0 ? `
                        <div class="flashcard-hints">
                            <button class="btn btn-sm" onclick="showHints()">💡 Show Hint</button>
                            <div id="hints-content" class="hidden">
                                ${card.hints.map(h => `<p class="hint">${h}</p>`).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>

            <button class="btn btn-primary btn-lg" onclick="revealAnswer('${card.id}')">
                👁️ Reveal Answer
            </button>
        </div>
    `;

    elements.flashcardCardDisplay.innerHTML = html;
}

// Show Hints
function showHints() {
    const hintsContent = document.getElementById('hints-content');
    if (hintsContent) {
        hintsContent.classList.toggle('hidden');
    }
}

// Reveal Answer
async function revealAnswer(cardId) {
    showLoading();

    try {
        const cardData = await apiRequest(`/flashcards/card/${cardId}/reveal`);
        hideLoading();

        const session = state.currentStudySession;
        const card = session.cards[state.currentCardIndex];

        let html = `
            <div class="flashcard-container">
                <div class="flashcard-progress">
                    Card ${state.currentCardIndex + 1} of ${session.cards.length}
                </div>

                <div class="flashcard revealed">
                    <div class="flashcard-front">
                        <span class="card-type-badge ${card.type}">${card.type.toUpperCase()}</span>
                        <div class="flashcard-content">
                            <p><strong>Q:</strong> ${cardData.front}</p>
                        </div>
                    </div>
                    <div class="flashcard-back">
                        <div class="flashcard-content">
                            <p><strong>A:</strong> ${cardData.back}</p>
                        </div>
                        ${cardData.source ? `
                            <div class="flashcard-source">
                                <small>📚 Source: ${cardData.source}</small>
                            </div>
                        ` : ''}
                    </div>
                </div>

                <div class="review-buttons">
                    <p>How well did you know this?</p>
                    <div class="quality-buttons">
                        <button class="btn btn-quality q0" onclick="submitReview('${cardId}', 0)">
                            😵 Blackout<br><small>0</small>
                        </button>
                        <button class="btn btn-quality q1" onclick="submitReview('${cardId}', 1)">
                            😕 Wrong<br><small>1</small>
                        </button>
                        <button class="btn btn-quality q2" onclick="submitReview('${cardId}', 2)">
                            🤔 Hard<br><small>2</small>
                        </button>
                        <button class="btn btn-quality q3" onclick="submitReview('${cardId}', 3)">
                            😐 Good<br><small>3</small>
                        </button>
                        <button class="btn btn-quality q4" onclick="submitReview('${cardId}', 4)">
                            🙂 Easy<br><small>4</small>
                        </button>
                        <button class="btn btn-quality q5" onclick="submitReview('${cardId}', 5)">
                            😄 Perfect<br><small>5</small>
                        </button>
                    </div>
                </div>
            </div>
        `;

        elements.flashcardCardDisplay.innerHTML = html;

    } catch (error) {
        hideLoading();
        alert('Failed to reveal answer: ' + error.message);
    }
}

// Submit Review
async function submitReview(cardId, quality) {
    const responseTime = Date.now() - state.studyStartTime;

    showLoading();

    try {
        await apiRequest('/flashcards/review', {
            method: 'POST',
            body: JSON.stringify({
                card_id: cardId,
                quality: quality,
                response_time_ms: responseTime
            })
        });

        hideLoading();

        // Move to next card
        state.currentCardIndex++;
        displayCurrentCard();

    } catch (error) {
        hideLoading();
        alert('Failed to submit review: ' + error.message);
    }
}

// End Study Session
function endStudySession() {
    const session = state.currentStudySession;

    elements.flashcardCardDisplay.innerHTML = `
        <div class="study-complete">
            <h3>🎉 Study Session Complete!</h3>
            <p>You reviewed ${session.cards.length} cards from "${session.deck_name}"</p>
            <button class="btn btn-primary" onclick="closeStudySession()">Done</button>
        </div>
    `;

    // Refresh decks to show updated stats
    loadFlashcardDecks();
}

// Close Study Session
function closeStudySession() {
    state.currentStudySession = null;
    state.currentCardIndex = 0;
    elements.flashcardStudyArea.classList.add('hidden');
    elements.flashcardCardDisplay.innerHTML = '';
}

// Delete Deck
async function deleteDeck(deckId) {
    if (!confirm('Are you sure you want to delete this deck? This cannot be undone.')) {
        return;
    }

    showLoading();

    try {
        await apiRequest(`/flashcards/deck/${deckId}`, {
            method: 'DELETE'
        });

        hideLoading();

        // Refresh decks
        await loadFlashcardDecks();

    } catch (error) {
        hideLoading();
        alert('Failed to delete deck: ' + error.message);
    }
}

// Load Flashcard Stats
async function loadFlashcardStats() {
    if (!state.studentId) return;

    try {
        const stats = await apiRequest(`/flashcards/stats/${state.studentId}`);

        if (stats.total_cards === 0) {
            elements.flashcardStats.innerHTML = `
                <div class="empty-state">
                    <p>Start studying to see your statistics!</p>
                </div>
            `;
            return;
        }

        elements.flashcardStats.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card">
                    <h4>Total Decks</h4>
                    <div class="value">${stats.total_decks}</div>
                </div>
                <div class="stat-card">
                    <h4>Total Cards</h4>
                    <div class="value">${stats.total_cards}</div>
                </div>
                <div class="stat-card">
                    <h4>Mastered</h4>
                    <div class="value">${stats.total_mastered}</div>
                </div>
                <div class="stat-card">
                    <h4>Due Now</h4>
                    <div class="value">${stats.total_due}</div>
                </div>
                <div class="stat-card">
                    <h4>Mastery Rate</h4>
                    <div class="value">${stats.mastery_percentage}%</div>
                </div>
                <div class="stat-card">
                    <h4>Reviews This Week</h4>
                    <div class="value">${stats.reviews_this_week}</div>
                </div>
                <div class="stat-card">
                    <h4>Accuracy This Week</h4>
                    <div class="value">${stats.accuracy_this_week}%</div>
                </div>
            </div>
        `;

    } catch (error) {
        console.error('Error loading flashcard stats:', error);
    }
}

// Make flashcard functions available globally
window.startStudySession = startStudySession;
window.revealAnswer = revealAnswer;
window.submitReview = submitReview;
window.closeStudySession = closeStudySession;
window.deleteDeck = deleteDeck;
window.showHints = showHints;

// ==================== CITATION DISPLAY IN CHAT ====================

// Enhanced chat message function with citation support
function addChatMessageWithCitations(role, content, citations = []) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;

    const strongTag = document.createElement('strong');
    strongTag.textContent = role === 'user' ? 'You:' : 'AI Tutor:';
    messageDiv.appendChild(strongTag);

    // Add main content
    const contentSpan = document.createElement('span');
    contentSpan.innerHTML = ' ' + content;
    messageDiv.appendChild(contentSpan);

    // Add citations if present
    if (citations && citations.length > 0) {
        const citationsDiv = document.createElement('div');
        citationsDiv.className = 'citations-container';
        citationsDiv.innerHTML = '<strong>Sources:</strong>';

        const citationsList = document.createElement('ul');
        citationsList.className = 'citations-list';

        citations.forEach((citation, index) => {
            const li = document.createElement('li');
            li.className = `citation-item source-${citation.source_type || 'unknown'}`;

            let sourceIcon = '📄';
            if (citation.source_type === 'DOCUMENT') sourceIcon = '📚';
            else if (citation.source_type === 'WEB') sourceIcon = '🌐';
            else if (citation.source_type === 'KNOWLEDGE_GRAPH') sourceIcon = '🔗';

            li.innerHTML = `
                <span class="citation-icon">${sourceIcon}</span>
                <span class="citation-title">${citation.title || citation.source || 'Source ' + (index + 1)}</span>
                ${citation.relevance_score ? `<span class="citation-score">(${Math.round(citation.relevance_score * 100)}% relevant)</span>` : ''}
            `;
            citationsList.appendChild(li);
        });

        citationsDiv.appendChild(citationsList);
        messageDiv.appendChild(citationsDiv);
    }

    elements.chatMessages.appendChild(messageDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

// Initialize flashcards when user logs in
async function initializeFlashcards() {
    await loadFlashcardDecks();
}

// Initialize
console.log('Agentic AI Tutor initialized');
