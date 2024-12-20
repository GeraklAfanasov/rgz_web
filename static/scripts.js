document.addEventListener('DOMContentLoaded', function () {
    const chatList = document.querySelector('#chat-list');
    const messagesContainer = document.querySelector('#messages-container');
    const sendMessageForm = document.querySelector('#message-form');
    const contentInput = document.querySelector('#content');
    const chatUsername = document.querySelector('#chat-username');
    const logoutBtn = document.querySelector('#logout-btn');

    let currentChatUserId = null;
    let unreadCounts = {};
    let lastMessageId = null;

    // Функция для загрузки списка пользователей
    async function loadUsers() {
        console.log("Loading users...");  // Логирование
        const response = await fetch('/users');
        if (response.ok) {
            const users = await response.json();
            console.log("Users loaded:", users);  // Логирование
            chatList.innerHTML = '';  // Очищаем список перед добавлением новых пользователей

            users.forEach(user => {
                const li = document.createElement('li');
                li.textContent = user.username;
                li.dataset.userId = user.id;
                li.addEventListener('click', () => loadChatMessages(user.id, user.username));

                // Добавляем изображение профиля, если оно есть
                if (user.profile_pic) {
                    const img = document.createElement('img');
                    img.src = `/static/profile_pics/${user.profile_pic}`;
                    img.alt = user.username;
                    img.classList.add('profile-pic');
                    li.prepend(img);
                } else {
                    console.log(`User ${user.username} has no profile picture.`);  // Логирование
                }

                const profileLink = document.createElement('a');
                profileLink.href = `/user/${user.id}`;
                profileLink.innerHTML = '<img src="/static/icons/gear.png" alt="View Profile" class="profile-icon">';
                profileLink.classList.add('profile-link');
                li.appendChild(profileLink);

                chatList.appendChild(li);

                const unreadCountSpan = document.createElement('span');
                unreadCountSpan.classList.add('unread-count');
                unreadCountSpan.textContent = unreadCounts[user.id] || 0;
                li.appendChild(unreadCountSpan);
            });
        } else {
            console.error('Error loading users');  // Логирование
            alert('Error loading users');
        }
    }

    // Функция для загрузки сообщений в чате
    async function loadChatMessages(receiverId, username) {
        currentChatUserId = receiverId;
        chatUsername.textContent = username;

        const response = await fetch(`/messages/${receiverId}`);
        if (response.ok) {
            const messages = await response.json();
            messagesContainer.innerHTML = '';
            messages.forEach(msg => {
                const messageClass = msg.sender === 'You' ? 'me' : 'user';
                const div = document.createElement('div');
                div.classList.add('message', messageClass);
                div.dataset.messageId = msg.id;

                const contentDiv = document.createElement('div');
                contentDiv.classList.add('message-content');
                contentDiv.textContent = msg.content;
                div.appendChild(contentDiv);

                if (msg.attachment) {
                    const img = document.createElement('img');
                    img.src = `/static/uploads/${msg.attachment}`;
                    img.alt = 'Attachment';
                    img.classList.add('message-attachment');
                    div.appendChild(img);
                }

                const timeSpan = document.createElement('span');
                timeSpan.classList.add('message-time');
                timeSpan.textContent = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                div.appendChild(timeSpan);

                if (sessionStorage.getItem('is_admin') === 'true' || msg.sender === 'You') {
                    const deleteBtn = document.createElement('button');
                    deleteBtn.textContent = 'Delete';
                    deleteBtn.classList.add('delete-message');
                    deleteBtn.addEventListener('click', () => deleteMessage(msg.id));
                    div.appendChild(deleteBtn);
                }

                messagesContainer.appendChild(div);
            });
            scrollToBottom();

            unreadCounts[receiverId] = 0;
            updateUnreadCounts();
        } else {
            alert('Error loading messages');
        }
    }

    function updateUnreadCounts() {
        const chatItems = document.querySelectorAll('#chat-list li');
        chatItems.forEach(item => {
            const userId = item.dataset.userId;
            const unreadCountSpan = item.querySelector('.unread-count');
            unreadCountSpan.textContent = unreadCounts[userId] || 0;
        });
    }

    function isAtBottom() {
        return messagesContainer.scrollHeight - messagesContainer.scrollTop === messagesContainer.clientHeight;
    }

    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    sendMessageForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!currentChatUserId) {
            alert('Please select a chat first.');
            return;
        }

        const content = contentInput.value;
        const formData = new FormData(sendMessageForm);
        formData.append('receiver_id', currentChatUserId);

        const response = await fetch('/messages', {
            method: 'POST',
            body: formData,
        });

        if (response.ok) {
            const data = await response.json();
            lastMessageId = data.message_id;

            contentInput.value = '';
            document.querySelector('#attachment').value = '';

            const receiverId = currentChatUserId;
            if (!unreadCounts[receiverId]) {
                unreadCounts[receiverId] = 0;
            }
            unreadCounts[receiverId]++;
            updateUnreadCounts();

            const newMessageDiv = document.createElement('div');
            newMessageDiv.classList.add('message', 'me');
            newMessageDiv.dataset.messageId = lastMessageId;

            const contentDiv = document.createElement('div');
            contentDiv.classList.add('message-content');
            contentDiv.textContent = content;
            newMessageDiv.appendChild(contentDiv);

            const timeSpan = document.createElement('span');
            timeSpan.classList.add('message-time');
            timeSpan.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            newMessageDiv.appendChild(timeSpan);

            const deleteBtn = document.createElement('button');
            deleteBtn.textContent = 'Delete';
            deleteBtn.classList.add('delete-message');
            deleteBtn.addEventListener('click', () => deleteMessage(lastMessageId));
            newMessageDiv.appendChild(deleteBtn);

            messagesContainer.appendChild(newMessageDiv);

            if (isAtBottom()) {
                scrollToBottom();
            }
        } else {
            const errorData = await response.json();
            alert(errorData.error || 'Error sending message.');
        }
    });

    logoutBtn.addEventListener('click', async () => {
        const response = await fetch('/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            currentChatUserId = null;
            unreadCounts = {};
            chatList.innerHTML = '';
            messagesContainer.innerHTML = '';
            chatUsername.textContent = 'Select a chat';
            window.location.href = '/login';
        } else {
            alert('Error logging out');
        }
    });

    async function deleteMessage(messageId) {
        const response = await fetch(`/messages/${messageId}`, {
            method: 'DELETE',
        });

        if (response.ok) {
            const messageDiv = document.querySelector(`.message[data-message-id="${messageId}"]`);
            if (messageDiv) {
                messageDiv.remove();
            }
        } else {
            alert('Error deleting message');
        }
    }

    // Вызываем функцию загрузки пользователей
    loadUsers();
});