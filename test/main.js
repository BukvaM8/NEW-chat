function submitForm(event) {
    event.preventDefault();
    document.getElementById('dialogForm').submit();
}

$(document).ready(function () {
    var dropdownVisible = false;

    // Скрываем dropdown при загрузке страницы
    $(".dropdown-menu").hide();

    // Обработчик события клика на изображении


    // Закрываем dropdown при клике вне его области
    // $(document).mouseup(function (e) {
    // var container = $(".dropdown-menu");
    //if (!container.is(e.target) && container.has(e.target).length === 0) {
    //  container.hide();
    //dropdownVisible = false;
    //}
    //});

    // Закрываем dropdown при повторном клике на изображение
    $(document).ready(function () {
        var dropdownVisible = false;

        $("#menuImage").on("click", function () {
            $(".dropdown-menu").toggle();
            dropdownVisible = !dropdownVisible;
        });

        $(document).on("mousedown", function (event) {
            if (!$(event.target).closest("#menuImage").length && !$(event.target).closest(".dropdown-menu").length) {
                if (dropdownVisible) {
                    $(".dropdown-menu").hide();
                    dropdownVisible = false;
                }
            }
        });

        $(".dropdown-menu").on("click", "li a", function () {
            $(".dropdown-menu").hide();
            dropdownVisible = false;
        });
    });

    $(document).ready(function () {
        $('#home-link').on('click', function (e) {
            e.preventDefault(); // Предотвратить стандартное поведение ссылки
            $.ajax({
                url: '/home', // URL для запроса данных главной страницы
                type: 'GET',
                success: function (response) {
                    $('.left-panel').html(response); // Замена содержимого левой панели
                },
                error: function () {
                    console.error('Ошибка при загрузке главной страницы');
                }
            });
        });
    });


    $("#contactImage").on("click", function () {
        $.ajax({
            url: '/contacts', // Путь к contacts.html
            type: 'GET',
            success: function (response) {
                $('.left-panel').html(response); // Заменить содержимое левой панели
            }
        });
    });
});
$(document).ready(function () {
    // Обработчик клика для ссылки профиля
    $("#profile-link").on("click", function (e) {
        e.preventDefault();
        loadProfile('/profile'); // Путь к profile2.html для ссылки профиля
    });

    // Обработчик клика для изображения профиля
    $(".profile-pic").on("click", function () {
        loadProfile('/profile'); // Путь к profile2.html для фотографии профиля
    });

    // Обработчик клика для никнейма пользователя
    $(".my_nickname").on("click", function () {
        loadProfile('/profile'); // Путь к profile2.html для никнейма
    });

    // Функция для загрузки профиля
    function loadProfile(url) {
        $.ajax({
            url: url,
            type: 'GET',
            success: function (response) {
                $('.left-panel').html(response); // Замена содержимого левой панели
            },
            error: function () {
                console.error('Ошибка при загрузке профиля');
            }
        });
    }
});


var ws;
var isEditingMessage = false;

function editMessage(messageIdStr) {
    console.log("Editing message with ID:", messageIdStr);
    const messageId = parseInt(messageIdStr, 10);
    if (isNaN(messageId)) {
        console.error(`Invalid messageId: ${messageIdStr}`);
        return;
    }

    let messageElement = document.querySelector(`[data-message-id="${messageId}"] .message-content`) ||
        document.querySelector(`[data-message-id="${messageId}"] .message-self`);

    if (!messageElement) {
        console.error("Message element not found for ID:", messageId);
        return;
    }

    // Извлечение текста сообщения
    let messageText = extractMessageText(messageElement);

    // Обновление формы ввода сообщения
    const textArea = document.querySelector('textarea[name="message"]');
    if (textArea) {
        textArea.value = messageText;
        const submitButton = document.querySelector('#message-form button[type="submit"]');
        if (submitButton) {
            submitButton.textContent = 'Сохранить';
            submitButton.onclick = function (e) {
                e.preventDefault();
                saveEditedMessage(messageId);
            };
        } else {
            console.error('Submit button not found');
        }
    } else {
        console.error('Textarea for message not found');
    }

    // Обновление имени файла в элементе отображения
    updateFileNameDisplayForEditing(messageElement);

    isEditingMessage = true;
}

function updateFileNameDisplayForEditing(messageElement) {
    const fileLinkElement = messageElement.querySelector('a[href^="/files/"]');
    const fileNameDisplay = document.getElementById('file-name-display');
    const fileName = fileLinkElement ? fileLinkElement.textContent : '';

    if (fileName) {
        fileNameDisplay.textContent = 'Выбранный файл: ' + fileName;
    } else {
        fileNameDisplay.textContent = '';
    }
}

function extractMessageText(messageElement) {
    let fullText = messageElement.textContent || '';
    const fileLinkElement = messageElement.querySelector('a[href^="/files/"]');

    if (fileLinkElement) {
        // Если есть файл, обрезаем текст до начала ссылки на файл
        const fileLinkIndex = fullText.indexOf(fileLinkElement.textContent);
        if (fileLinkIndex !== -1) {
            fullText = fullText.substring(0, fileLinkIndex);
        }
    }

    // Удаление служебных слов и фраз
    const serviceWords = ["Переслать", "Изменить", "Удалить сообщение", "Отправлено:", "None"];
    serviceWords.forEach(word => {
        fullText = fullText.replace(new RegExp(word, 'g'), '');
    });

    return fullText.trim();
}


function saveEditedMessage(messageId) {
    const newMessageText = document.querySelector('textarea[name="message"]').value;
    const currentDate = new Date().toLocaleString();

    // Отправка обновленного сообщения через WebSocket
    ws.send(JSON.stringify({
        action: 'edit_message',
        message_id: messageId,
        new_text: newMessageText
    }));

    // Обновление элемента сообщения в DOM
    let messageElement = document.querySelector(`[data-message-id="${messageId}"] .message-content`) ||
        document.querySelector(`[data-message-id="${messageId}"] .message-self`);

    if (messageElement) {
        // Очистка текущего текста сообщения
        messageElement.innerHTML = '';

        // Добавление нового текста сообщения
        const newTextElement = document.createElement('div');
        newTextElement.textContent = newMessageText;
        messageElement.appendChild(newTextElement);

        // Добавление метки "Изменено"
        const editedMark = document.createElement('span');
        editedMark.className = 'edited-mark';
        editedMark.textContent = ` Изменено: ${currentDate}`;
        messageElement.appendChild(editedMark);

        // Восстановление выпадающего меню
        const dropdownMenu = messageElement.querySelector('.message-dropdown');
        if (dropdownMenu) {
            messageElement.appendChild(dropdownMenu);
        }
    }

    // Сброс состояния редактирования
    resetEditingState();
}

function resetEditingState() {
    // Обновление кнопки отправки и очистка поля ввода сообщения
    const submitButton = document.querySelector('#message-form button[type="submit"]');
    submitButton.textContent = 'Отправить';
    submitButton.onclick = null;
    document.querySelector('textarea[name="message"]').value = '';

    // Сброс флага редактирования
    isEditingMessage = false;

    // Очистка отображения имени файла
    const fileNameDisplay = document.getElementById('file-name-display');
    if (fileNameDisplay) {
        fileNameDisplay.textContent = '';
    }
}


function updateDropdownMenuHandlers(dropdownMenu, messageId) {
    const deleteButton = dropdownMenu.querySelector('.dropdown-item.delete-message-button');
    const editButton = dropdownMenu.querySelector('.dropdown-item.edit-message-button');

    // Обновление обработчиков событий для кнопок
    if (deleteButton) {
        deleteButton.onclick = function () {
            deleteMessage(messageId.toString());
        };
    }

    if (editButton) {
        editButton.onclick = function () {
            editMessage(messageId.toString());
        };
    }
}


function createDropdownMenu(messageElement, messageId) {
    // Создание выпадающего меню
    const dropdown = document.createElement('div');
    dropdown.className = 'message-dropdown';

    const dropdownIcon = document.createElement('img');
    dropdownIcon.src = '/static/downarrow.png';
    dropdownIcon.alt = 'Options';
    dropdownIcon.className = 'message-options-icon';
    dropdownIcon.onclick = function (event) {
        toggleDropdownMenu(event);
    };

    const dropdownContent = document.createElement('div');
    dropdownContent.className = 'message-options';
    dropdownContent.style.display = 'none';

    // Создание кнопки "Удалить сообщение"
    const deleteButton = document.createElement('button');
    deleteButton.className = 'dropdown-item delete-message-button';
    deleteButton.textContent = 'Удалить сообщение';
    deleteButton.onclick = function () {
        deleteMessage(messageId.toString());
    };

    // Создание кнопки "Изменить"
    const editButton = document.createElement('button');
    editButton.className = 'dropdown-item edit-message-button';
    editButton.textContent = 'Изменить';
    editButton.onclick = function () {
        editMessage(messageId.toString());
    };

    dropdownContent.appendChild(deleteButton);
    dropdownContent.appendChild(editButton);
    dropdown.appendChild(dropdownIcon);
    dropdown.appendChild(dropdownContent);
    messageElement.appendChild(dropdown);
}

// Инициализация кода для dialogs.html
function initializeDialogJS(dialogId, currentUserId) {  // Добавлен параметр currentUserId
    const cookie = document.cookie.split('; ').find(row => row.startsWith('access_token='));
    const access_token = cookie ? cookie.split('=')[1] : null;
    ws = new WebSocket(`ws://127.0.0.1:8080/ws/dialogs/${dialogId}/`);

    ws.onopen = function (event) {
        console.log("WebSocket connection opened.", event);
        ws.send(JSON.stringify({"action": "init_connection", "dialog_id": dialogId, "access_token": access_token}));
    };

    // Автоматическая плавная прокрутка к последнему сообщению
    const messagesList = document.querySelector('.list-group');
    const lastMessage = messagesList.lastElementChild;
    if (lastMessage) {
        lastMessage.scrollIntoView();
    }


    // Динамическое изменение размера текстовой области:
    document.addEventListener('DOMContentLoaded', function () {
        const textArea = document.getElementById('message-input');

        const updateTextAreaHeight = () => {
            textArea.style.overflowY = 'hidden'; // Скрыть временно скроллбар
            const maxHeight = 150; // Максимальная высота

            if (textArea.scrollHeight > maxHeight) {
                textArea.style.height = maxHeight + 'px';
                textArea.style.overflowY = 'scroll'; // Показать скроллбар если текст превышает максимальную высоту
            } else {
                textArea.style.height = textArea.scrollHeight + 'px'; // Установить высоту, соответствующую содержимому
            }
        };

        textArea.addEventListener('input', updateTextAreaHeight);
        updateTextAreaHeight(); // Установить начальную высоту при загрузке страницы
    });


    // Обработчик события нажатия клавиши в текстовом поле формы
    const textArea = document.querySelector('textarea[name="message"]');
    textArea.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            if (isEditingMessage) {
                // Пользователь находится в режиме редактирования
                e.preventDefault(); // предотвращаем отправку формы
                const messageId = document.querySelector('.message-item[data-editing="true"]')?.dataset.messageId;
                if (messageId) {
                    saveEditedMessage(parseInt(messageId, 10));
                }
            } else {
                // Обычный режим отправки сообщений
                e.preventDefault(); // предотвращаем перевод строки
                document.getElementById('message-form').dispatchEvent(new Event('submit'));
            }
        }
    });


    // Функция отправки сообщения
    const form = document.getElementById('message-form');
    form.addEventListener('submit', function (e) {
        e.preventDefault();
        const formData = new FormData(form);

        fetch(`/dialogs/${dialogId}/send_message`, {
            method: 'POST',
            body: formData
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to send message');
                }
                return response.json();
            })
            .then(data => {
                if (data && data.message_id) {
                    const messagesList = document.querySelector('.list-group');
                    const newMessage = document.createElement('li');
                    newMessage.className = "message-item user";
                    newMessage.dataset.messageId = data.message_id;

                    const messageContent = document.createElement('div');
                    messageContent.className = "message-content";
                    messageContent.dataset.messageId = data.message_id;

                    // Создаем и добавляем текстовый узел для текста сообщения
                    const messageTextNode = document.createTextNode(data.message_text);
                    messageContent.appendChild(messageTextNode);

                    // Создаем и добавляем выпадающее меню
                    createDropdownMenu(messageContent, data.message_id);

                    newMessage.appendChild(messageContent);
                    messagesList.appendChild(newMessage);

                    // Прокрутка к последнему сообщению
                    messagesList.scrollTop = messagesList.scrollHeight;
                }

                // Очищаем поля ввода после отправки
                form.querySelector('textarea[name="message"]').value = '';
                const fileInput = form.querySelector('input[type="file"]');
                if (fileInput) {
                    fileInput.value = '';
                    resetFileNameDisplay(); // Сброс отображения имени файла
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
    });

// Функция для сброса отображения имени файла
    function resetFileNameDisplay() {
        var fileNameDisplay = document.getElementById('file-name-display');
        if (fileNameDisplay) {
            fileNameDisplay.textContent = '';
        }
    }

    ws.onmessage = function (event) {
        console.log("Получено сообщение через WebSocket:", event.data);
        let messageData;
        try {
            messageData = JSON.parse(event.data);
            console.log("Разобранное сообщение:", messageData);
        } catch (e) {
            console.error("Invalid JSON", e);
            return;
        }

        const action = messageData.action;

        if (action === 'new_token') {
            document.cookie = "access_token=" + messageData.token;

        } else if (action === 'message_deleted') {
            const messageId = messageData.message_id;
            console.log("Attempting to delete message with ID:", messageId);
            const messageElement = document.querySelector(`.message-item[data-message-id="${messageId}"], .message-self[data-message-id="${messageId}"]`);
            if (messageElement) {
                console.log(`Deleting message with id: ${messageId}`);
                messageElement.remove();
            } else {
                console.warn(`Message with id: ${messageId} not found for deletion`);
            }
        } else if (action === 'message_updated') {
            const messageId = messageData.message_id;
            const newMessageText = messageData.new_text;
            const editTimestamp = messageData.edit_timestamp;

            let messageElement = document.querySelector(`.message-item[data-message-id="${messageId}"] .message-content`) ||
                document.querySelector(`.message-self[data-message-id="${messageId}"]`);

            if (messageElement) {
                // Очистка текущего содержимого сообщения, кроме выпадающего меню
                const dropdownMenu = messageElement.querySelector('.message-dropdown');
                messageElement.innerHTML = '';

                // Добавление нового текста сообщения
                const newTextElement = document.createElement('div');
                newTextElement.textContent = newMessageText;
                messageElement.appendChild(newTextElement);

                // Добавление метки "Изменено"
                const editedMark = document.createElement('span');
                editedMark.className = 'edited-mark';
                editedMark.textContent = ` Изменено: ${new Date(editTimestamp).toLocaleString()}`;
                messageElement.appendChild(editedMark);

                // Восстановление выпадающего меню
                if (dropdownMenu) {
                    // Обновление обработчиков событий для кнопок в dropdown меню
                    updateDropdownMenuHandlers(dropdownMenu, messageId);
                    messageElement.appendChild(dropdownMenu);
                } else {
                    // Если выпадающего меню нет, создать его
                    createDropdownMenu(messageElement, messageId);
                }
            }
        } else if (action === 'update_last_dialog_message') {
            console.log("Обновление последнего сообщения для диалога:", messageData.dialog_id);

            const dialogElement = document.querySelector(`.clickable-dialog[data-dialog-id="${messageData.dialog_id}"]`);
            if (dialogElement) {
                let lastMessageElement = dialogElement.querySelector('.last_message');

                let messageText = messageData.last_message;
                // Проверка наличия информации о файле в сообщении
                if (messageText.includes('[[FILE]]') && messageText.includes('[[/FILE]]')) {
                    const [text, fileInfo] = messageText.split('[[FILE]]');
                    const fileName = fileInfo.split('[[/FILE]]')[0].split(', File Path: ')[1];
                    messageText = text + (fileName ? " (Файл: " + fileName + ")" : ""); // Конкатенация текста сообщения и имени файла
                }

                if (lastMessageElement) {
                    console.log("Обновляем существующий элемент последнего сообщения");
                    lastMessageElement.textContent = messageText;
                } else {
                    console.log("Создаем новый элемент последнего сообщения");
                    lastMessageElement = document.createElement('small');
                    lastMessageElement.classList.add('last_message');
                    lastMessageElement.textContent = messageText;
                    dialogElement.appendChild(lastMessageElement);
                }
            }
        } else if (messageData.message && messageData.message.sender_id) {
            const currentUserId = "{{ current_user.id }}";
            const newMessage = document.createElement('li');
            newMessage.className = messageData.message.sender_id === parseInt(currentUserId) ? "message-item user" : "message-item";
            newMessage.dataset.messageId = String(messageData.message.message_id);

            const messageContent = document.createElement('div');
            messageContent.className = messageData.message.sender_id === parseInt(currentUserId) ? "message-self" : "message-content";

            const senderNickname = messageData.message.sender_nickname || "";
            const rawMessage = messageData.message.message;


            if (senderNickname) {
                const senderElement = document.createElement('strong');
                senderElement.innerText = senderNickname + ":";
                messageContent.appendChild(senderElement);
            }

            const messageTextElement = document.createElement('div');
            if (rawMessage.includes('[[FILE]]') && rawMessage.includes('[[/FILE]]')) {
                const [text, fileInfo] = rawMessage.split('[[FILE]]');
                const cleanedFileInfo = fileInfo.replace('[[/FILE]]', '');
                const [fileIdInfo, fileNameInfo] = cleanedFileInfo.split(', ');
                const fileId = fileIdInfo.split(': ')[1];
                const fileName = fileNameInfo.split(': ')[1];

                messageTextElement.appendChild(document.createTextNode(" " + text));
                messageContent.appendChild(messageTextElement);

                const fileLink = document.createElement('div');
                const fileAnchor = document.createElement('a');
                fileAnchor.href = `/files/${fileId}`;
                fileAnchor.innerText = fileName;
                fileLink.appendChild(fileAnchor);
                messageContent.appendChild(fileLink);
            } else {
                messageTextElement.appendChild(document.createTextNode(" " + rawMessage));
                messageContent.appendChild(messageTextElement);
            }

            const timeElement = document.createElement('div');
            if (messageData.message.timestamp) {
                timeElement.appendChild(document.createTextNode("Отправлено: " + messageData.message.timestamp));
            } else {
                timeElement.appendChild(document.createTextNode("Время отправки не указано"));
            }
            messageContent.appendChild(timeElement);

            const dropdown = document.createElement('div');
            dropdown.className = 'message-dropdown';

            const dropdownIcon = document.createElement('img');
            dropdownIcon.src = '/static/downarrow.png';
            dropdownIcon.alt = 'Options';
            dropdownIcon.className = 'message-options-icon';
            dropdownIcon.onclick = function (event) {
                toggleDropdownMenu(event);
            };

            const dropdownContent = document.createElement('div');
            dropdownContent.className = 'message-options';
            dropdownContent.style.display = 'none';

            const deleteButton = document.createElement('button');
            deleteButton.className = 'dropdown-item';
            deleteButton.textContent = 'Удалить сообщение';
            deleteButton.onclick = function () {
                deleteMessage(messageData.message.message_id.toString());
            };
            dropdownContent.appendChild(deleteButton);

            const editButton = document.createElement('button');
            editButton.className = 'dropdown-item';
            editButton.textContent = 'Изменить';
            editButton.onclick = function () {
                editMessage(messageData.message.message_id.toString());
            };
            dropdownContent.appendChild(editButton);

            const forwardButton = document.createElement('button');
            forwardButton.className = 'dropdown-item';
            forwardButton.textContent = 'Переслать';
            dropdownContent.appendChild(forwardButton);

            dropdown.appendChild(dropdownIcon);
            dropdown.appendChild(dropdownContent);
            messageContent.appendChild(dropdown);

            newMessage.appendChild(messageContent);
            const messagesList = document.querySelector('.list-group');
            messagesList.appendChild(newMessage);

            setTimeout(() => {
                messagesList.scrollTop = messagesList.scrollHeight;
            }, 100);
        }
    };
}

function updateFileNameDisplay() {
    var fileInput = document.getElementById('fileInput');
    var fileNameDisplay = document.getElementById('file-name-display');

    if (fileInput.files.length > 0) {
        var fileNames = [];
        for (var i = 0; i < fileInput.files.length; i++) {
            fileNames.push(fileInput.files[i].name);
        }
        fileNameDisplay.textContent = 'Выбранные файлы: ' + fileNames.join(', ');
    } else {
        fileNameDisplay.textContent = '';
    }
}

// Функции для работы с сообщениями
function deleteMessage(messageIdStr) {
    console.log("Deleting message with ID:", messageIdStr); // Для отладки
    const messageId = parseInt(messageIdStr, 10);
    if (isNaN(messageId)) {
        console.error(`Invalid messageId: ${messageIdStr}`);
        return;
    }

    const deleteRequest = JSON.stringify({action: 'delete_message', message_id: messageId});
    ws.send(deleteRequest);
}


function toggleDropdownMenu(event) {
    event.stopPropagation(); // Предотвращаем всплытие события
    const dropdownMenu = event.target.nextElementSibling;
    const isDisplayed = dropdownMenu.style.display === 'block';

    // Закрыть все открытые выпадающие меню перед открытием нового
    closeAllDropdowns();

    // Переключить состояние выбранного выпадающего списка
    dropdownMenu.style.display = isDisplayed ? 'none' : 'block';

    // Закрытие выпадающего списка при убирании курсора
    dropdownMenu.onmouseleave = function () {
        dropdownMenu.style.display = 'none';
    };
}

function closeAllDropdowns() {
    const allDropdowns = document.querySelectorAll('.message-options');
    allDropdowns.forEach(function (menu) {
        menu.style.display = 'none';
    });
}

// Обработчик клика вне выпадающего списка
document.addEventListener('click', function (event) {
    if (!event.target.matches('.message-options-icon')) {
        closeAllDropdowns();
    }
});


// Функция для открытия шторки с профилем пользователя
function openUserProfileSidebar(phoneNumber, dialogId) {  // Добавлен dialogId как параметр
    let userProfileSidebar = document.getElementById('user-profile-sidebar');
    if (!userProfileSidebar) {
        userProfileSidebar = document.createElement('div');
        userProfileSidebar.id = 'user-profile-sidebar';
        userProfileSidebar.classList.add('user-profile-sidebar');
        document.body.appendChild(userProfileSidebar);
    }

    // AJAX запрос для получения HTML-кода профиля
    fetch(`/profile/${phoneNumber}?dialogId=${dialogId}`)  // Передаем dialogId в запросе
        .then(response => response.text())
        .then(html => {
            userProfileSidebar.innerHTML = html;
            userProfileSidebar.classList.add('open');
            activateUserProfileScripts(dialogId);  // Передаем dialogId в функцию активации скриптов
        })
        .catch(error => console.error('Error:', error));
}


// Функция для обработки клика на шапку диалога
function handleInterlocutorInfoClick(event) {
    event.preventDefault();
    const dialogContainer = event.currentTarget.closest('.container');
    const dialogId = dialogContainer.querySelector('input[name="dialog_id"]').value;
    const phoneNumber = dialogContainer.querySelector('.username a').getAttribute('href').split('/').pop();
    const userProfileSidebar = document.getElementById('user-profile-sidebar');

    // Проверяем, открыта ли шторка
    if (userProfileSidebar && userProfileSidebar.classList.contains('open')) {
        closeUserProfileSidebar(); // Закрываем шторку, если она открыта
    } else {
        openUserProfileSidebar(phoneNumber, dialogId); // Открываем шторку, если она закрыта
    }
}


// Функция для обработки клика на никнейм пользователя
function handleUsernameClick(event) {
    event.preventDefault();
    event.stopPropagation(); // Добавлено для предотвращения всплытия события

    const userProfileSidebar = document.getElementById('user-profile-sidebar');
    // Проверяем, открыта ли шторка
    if (userProfileSidebar && userProfileSidebar.classList.contains('open')) {
        closeUserProfileSidebar(); // Закрываем шторку, если она открыта
    } else {
        const phoneNumber = event.target.getAttribute('href').split('/').pop();
        const dialogId = document.querySelector('input[name="dialog_id"]').value;
        openUserProfileSidebar(phoneNumber, dialogId); // Открываем шторку, если она закрыта
    }
}

// Добавление обработчика клика на шапку диалога
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.interlocutor-info, .interlocutor-info *').forEach(function (element) {
        element.addEventListener('click', function (event) {
            event.preventDefault();
            const dialogContainer = this.closest('.container');
            const dialogId = dialogContainer.querySelector('input[name="dialog_id"]').value;
            const phoneNumber = dialogContainer.querySelector('.username a').getAttribute('href').split('/').pop();
            openUserProfileSidebar(phoneNumber, dialogId);
        });
    });
});


document.addEventListener('DOMContentLoaded', function () {
    const usernameLink = document.querySelector('.username a');
    if (usernameLink) {
        usernameLink.addEventListener('click', function (event) {
            event.preventDefault();
            openUserProfileSidebar();
        });
    } else {
        console.error('Элемент с классом .username a не найден');
    }
});


// Добавьте обработчик клика на элемент с никнеймом пользователя
document.addEventListener('click', function (event) {
    if (event.target.matches('.username')) {
        event.preventDefault();
        const phoneNumber = event.target.getAttribute('href').split('/').pop();
        openUserProfileSidebar(phoneNumber);
    }
});


// Функция для закрытия шторки
function closeUserProfileSidebar() {
    const userProfileSidebar = document.getElementById('user-profile-sidebar');
    if (userProfileSidebar) {
        userProfileSidebar.classList.remove('open');
    }
}

// Добавление обработчика событий для закрытия шторки при клике вне её области
document.addEventListener('click', function (event) {
    const userProfileSidebar = document.getElementById('user-profile-sidebar');
    // Проверяем, что шторка открыта и клик произошел вне её области
    if (userProfileSidebar && userProfileSidebar.classList.contains('open') && !userProfileSidebar.contains(event.target)) {
        closeUserProfileSidebar();
    }
});

// Обновленный обработчик событий для кнопки "стрелка влево" внутри шторки
document.addEventListener('click', function (event) {
    if (event.target.closest('.user-profile-sidebar .fas.fa-arrow-left')) {
        event.preventDefault(); // Предотвращаем переход по ссылке
        closeUserProfileSidebar();
    }
});


// Функция для удаления диалога
function deleteDialog(dialogId) {
    fetch(`/dialogs/${dialogId}/delete_post`, {
        method: 'POST'
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to delete dialog');
            }
            // Обработка после успешного удаления
            window.location.href = '/home';
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

// Активация скриптов внутри шторки
function activateUserProfileScripts(dialogId) {
    const deleteDialogButton = document.getElementById('delete-dialog-button');
    if (deleteDialogButton) {
        deleteDialogButton.setAttribute('data-dialog-id', dialogId); // Установка dialogId
        deleteDialogButton.addEventListener('click', function () {
            deleteDialog(dialogId);
        });
    }
}


// Загрузка dialogs.html в правую панель
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.clickable-dialog').forEach(function (container) {
        container.addEventListener('click', function (event) {
            if (event.target.classList.contains('load-dialog')) return;
            const dialogId = event.currentTarget.getAttribute('data-dialog-id');
            const currentUserId = "{{ current_user.id }}"; // Получение ID текущего пользователя

            fetch(`/dialogs/${dialogId}`)
                .then(response => {
                    if (response.status == 410) { // Dialog was deleted by the user
                        // Здесь можно добавить логику для обработки удаленных диалогов, например, удалить элемент из списка
                        console.error('Dialog was deleted by both users.');
                    } else if (!response.ok) {
                        throw new Error(`Server responded with status: ${response.status}`);
                    }
                    return response.text();
                })
                .then(html => {
                    document.querySelector('#dialog-panel').innerHTML = html;
                    initializeDialogJS(dialogId, currentUserId);
                })
                .catch(error => {
                    console.error('Ошибка:', error);
                });
        });
    });
});


// Инициализация кода для create_dialog.html
function initializeCreateDialogJS() {
    document.querySelectorAll('.start-dialog-form').forEach(function (form) {
        form.addEventListener('submit', function (event) {
            event.preventDefault();
            const userId = form.action.split('/').pop();

            fetch(`/create_dialog/${userId}`, {
                method: 'POST'
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`Server responded with status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.error) {
                        console.error('Server error:', data.error);
                    } else if (data.dialog_id) {
                        const dialogId = data.dialog_id;

                        // Загружаем содержимое dialogs.html в правую панель
                        fetch(`/dialogs/${dialogId}`)
                            .then(response => response.text())
                            .then(html => {
                                document.querySelector('#dialog-panel').innerHTML = html;
                                initializeDialogJS(dialogId);
                            });
                    } else {
                        throw new Error('Invalid response from server');
                    }
                })
                .catch(error => {
                    console.error('Ошибка:', error);
                });
        });
    });
}


// Добавление обработчика для кнопки "Создать новый диалог"
document.addEventListener('DOMContentLoaded', function () {
    const createDialogLink = document.querySelector('.create-dialog-link');
    if (createDialogLink) {
        createDialogLink.addEventListener('click', function (event) {
            event.preventDefault();  // Отменяем стандартное поведение перехода по ссылке

            // Загружаем содержимое create_dialog.html
            fetch('/create_dialog')
                .then(response => response.text())
                .then(html => {
                    // Вставляем HTML в правую панель
                    document.querySelector('#dialog-panel').innerHTML = html;

                    // Инициализируем JS для create_dialog.html (если необходимо)
                    initializeCreateDialogJS();
                })
                .catch(error => {
                    console.error('Ошибка:', error);
                });
        });
    }
});


// Инициализация кода для dialogs.html
// ... (ваш текущий код для dialogs)

// Загрузка chat.html в правую панель
document.querySelectorAll('.clickable-chat').forEach(function (container) {
    container.addEventListener('click', function (event) {
        if (event.target.classList.contains('load-chat')) return;

        const chatId = event.currentTarget.getAttribute('data-chat-id');
        console.log(`Переключение на чат с ID: ${chatId}`);

        fetch(`/chat/${chatId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Ошибка при загрузке чата');
                }
                return response.text();
            })
            .then(html => {
                document.querySelector('#dialog-panel').innerHTML = html;
                initializeChatJS(chatId); // Вызывайте initializeChatJS после того, как HTML чата вставлен в DOM
            })
            .catch(error => {
                console.error('Ошибка:', error);
            });
    });
});

// Инициализация кода для chat.html
function initializeChatJS(chatId) {

    const cookie = document.cookie.split('; ').find(row => row.startsWith('access_token='));
    const access_token = cookie ? cookie.split('=')[1] : null;
    var ws = new WebSocket(`ws://127.0.0.1:8080/ws/chats/${chatId}/`);

    ws.onopen = function (event) {
        console.log("WebSocket connection opened.", event);
        ws.send(JSON.stringify({"action": "init_connection", "chat_id": chatId, "access_token": access_token}));
    };

    ws.onclose = function (event) {
        console.log("WebSocket connection closed:", event);
    };

    ws.onerror = function (error) {
        console.log(`WebSocket Error: ${error}`);
    };

    // Автоматическая плавная прокрутка к последнему сообщению
    const messagesList = document.getElementById('chat-history');
    const lastMessage = messagesList.lastElementChild;
    if (lastMessage) {
        lastMessage.scrollIntoView();
    }


    // Инициализация модального окна для добавления участников
    const addParticipantButton = document.getElementById('addParticipantButton');
    const modal = $('#addParticipantModal');
    const contactsListDiv = document.getElementById('contactsList');

    addParticipantButton.addEventListener('click', function () {
        modal.modal('show');
        fetch(`/api/contacts/`)
            .then(response => response.json())
            .then(contacts => {
                contactsListDiv.innerHTML = contacts.map(contact => `
                <div class="contact-item">
                    <span>${contact.fio} (${contact.nickname})</span>
                    <button class="btn btn-sm btn-primary add-to-chat" data-phone-number="${contact.phone_number}">Добавить</button>
                </div>
            `).join('');
            })
            .catch(error => console.error('Ошибка:', error));
    });

    contactsListDiv.addEventListener('click', function (event) {
        if (event.target.classList.contains('add-to-chat')) {
            const phoneNumber = event.target.getAttribute('data-phone-number');
            fetch(`/chat/${chatId}/members/${phoneNumber}/add`, {method: 'POST'})
                .then(response => {
                    if (response.ok) {
                        console.log('Участник добавлен в чат');
                        event.target.disabled = true;
                    } else {
                        console.error('Ошибка при добавлении участника');
                    }
                })
                .catch(error => console.error('Ошибка:', error));
        }
    });

    document.addEventListener('submit', function (event) {
        const form = event.target;
        if (form && form.action && form.action.endsWith(`/chats/${chatId}/send_message`)) {
            event.preventDefault();
            const formData = new FormData(form);

            fetch(form.action, {
                method: 'POST',
                body: formData
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        console.log('Сообщение успешно отправлено. Message ID:', data.message.id);
                        // Дополнительные действия после отправки сообщения
                        const lastMessage = document.querySelector('.messages-list .message-item:last-child');
                        if (lastMessage) {
                            lastMessage.dataset.messageId = data.message.id;
                            console.log('Message ID установлен для нового сообщения:', data.message.id);
                        }

                        // Очистка формы
                        form.reset();

                        // Очистка области отображения информации о файле
                        const fileDisplayArea = document.getElementById('file-display-area');
                        if (fileDisplayArea) {
                            fileDisplayArea.innerHTML = '';
                        }
                    } else {
                        console.log('Ошибка при отправке сообщения:', data.error);
                    }
                })
                .catch(error => {
                    console.error('Ошибка при отправке формы:', error);
                });
        }
    });


    document.getElementById('file').addEventListener('click', function () {
        document.getElementById('file-input').click();
    });

    document.getElementById('file-input').addEventListener('change', function () {
        const fileDisplayArea = document.getElementById('file-display-area');
        fileDisplayArea.innerHTML = '';

        const file = this.files[0];
        if (file) {
            const fileInfoDiv = document.createElement('div');
            fileInfoDiv.textContent = `Прикрепленный файл: ${file.name}`;
            fileDisplayArea.appendChild(fileInfoDiv);
        }
    });


    function editChatMessage(messageId) {
        const messageElement = document.querySelector(`.message-item[data-message-id="${messageId}"]`);
        if (!messageElement) {
            console.error("Message element not found for ID:", messageId);
            return;
        }

        let messageTextElement = messageElement.querySelector('.message-content p') || messageElement.querySelector('.message-content div');
        if (!messageTextElement) {
            console.error("Message text element not found for ID:", messageId);
            return;
        }

        const messageInput = document.getElementById('message-input');
        const submitButton = document.getElementById('send-button');

        messageInput.value = messageTextElement.textContent.trim();
        submitButton.textContent = 'Сохранить';
        submitButton.onclick = function (e) {
            e.preventDefault();
            saveEditedChatMessage(messageId, messageTextElement, messageElement); // Передача messageElement как аргумента
        };
    }

    function saveEditedChatMessage(messageId, messageTextElement, messageElement) {
        const newMessageText = document.getElementById('message-input').value.trim();
        ws.send(JSON.stringify({
            "action": "edit_message",
            "message_id": messageId,
            "new_text": newMessageText
        }));

        // Сохранение ссылки на выпадающее меню, если оно существует
        let dropdownMenu = messageElement.querySelector('.message-dropdown');

        // Обновление только текста сообщения
        if (messageTextElement) {
            messageTextElement.textContent = newMessageText;
        }

        // Создание или обновление метки об изменении сообщения
        let editMark = messageElement.querySelector('.edit-mark');
        if (!editMark) {
            editMark = document.createElement('div');
            editMark.className = 'edit-mark';
            messageElement.querySelector('.message-content').appendChild(editMark);
        }
        editMark.textContent = `Изменено: ${new Date().toLocaleString()}`;

        // Восстановление выпадающего меню после обновления текста сообщения
        if (dropdownMenu) {
            messageElement.appendChild(dropdownMenu);
        } else {
            // Если выпадающего меню нет, создать его
            createOrUpdateDropdownMenu(messageElement, messageId);
        }

        // Сброс формы
        document.getElementById('message-input').value = '';
        document.getElementById('send-button').textContent = 'Отправить';
        document.getElementById('send-button').onclick = null;
    }

    function createOrUpdateDropdownMenu(messageElement, messageId) {
        let dropdown = messageElement.querySelector('.message-dropdown');
        if (!dropdown) {
            // Если выпадающего списка нет, создать его
            dropdown = document.createElement('div');
            dropdown.className = 'message-dropdown';
            messageElement.appendChild(dropdown);
        }

        // Создание кнопки удаления, если она еще не существует
        let deleteButton = dropdown.querySelector('.delete-message-button');
        if (!deleteButton) {
            deleteButton = document.createElement('button');
            deleteButton.className = 'dropdown-item delete-message-button';
            deleteButton.textContent = 'Удалить сообщение';
            deleteButton.onclick = function () {
                ws.send(JSON.stringify({"action": "delete_message", "message_id": messageId}));
            };
            dropdown.appendChild(deleteButton);
        }

        // Создание кнопки редактирования, если она еще не существует
        let editButton = dropdown.querySelector('.edit-message-button');
        if (!editButton) {
            editButton = document.createElement('button');
            editButton.className = 'dropdown-item edit-message-button';
            editButton.textContent = 'Редактировать';
            editButton.onclick = function () {
                editChatMessage(messageId);
            };
            dropdown.appendChild(editButton);
        }

    }


    // Обработчик клика в правой панели для управления выпадающими списками и кнопками в сообщениях
    document.querySelector('.right-panel').addEventListener('click',
        function (event) {
            // Сброс `z-index` для всех элементов сообщений
            document.querySelectorAll('.message-item').forEach(function (messageItem) {
                messageItem.style.zIndex = 1;
            });

            // Закрытие всех открытых выпадающих списков
            document.querySelectorAll('.message-options').forEach(function (dropdown) {
                dropdown.style.display = 'none';
            });

            // Проверка клика по иконке выпадающего списка
            if (event.target.closest('.message-options-icon')) {
                const messageOptions = event.target.closest('.message-dropdown').querySelector('.message-options');
                const messageItem = event.target.closest('.message-item');

                messageOptions.style.display = messageOptions.style.display === 'none' ? 'block' : 'none';
                messageItem.style.zIndex = messageOptions.style.display === 'block' ? 10000 : 1;
            }

            // Обработчик клика для кнопки "Удалить сообщение"
            if (event.target.closest('.delete-message-button')) {
                const messageElement = event.target.closest('.message-item');
                const messageId = messageElement ? messageElement.dataset.messageId : null;
                if (messageId) {
                    const messageIdNumber = parseInt(messageId, 10);
                    ws.send(JSON.stringify({"action": "delete_message", "message_id": messageIdNumber}));
                }
            }

            if (event.target.classList.contains('edit-message-button')) {
                const messageId = event.target.closest('.message-item').dataset.messageId;
                editChatMessage(messageId);
            }

        });

    // Обработчик клика в списке сообщений для обработки удаления сообщений
    document.querySelector('.messages-list').addEventListener('click', function (event) {
        if (event.target.className === 'dropdown-item' && event.target.textContent === 'Удалить сообщение') {
            const messageElement = event.target.closest('.message-item');
            const messageId = messageElement ? messageElement.dataset.messageId : null;
            if (messageId) {
                const messageIdNumber = parseInt(messageId, 10);
                ws.send(JSON.stringify({"action": "delete_message", "message_id": messageIdNumber}));
            }
        }
    });

    ws.onmessage = function (event) {
        console.log("Получено сообщение через WebSocket:", event.data);

        let messageData;
        try {
            messageData = JSON.parse(event.data);
        } catch (e) {
            console.error("Invalid JSON", e);
            return;
        }

        const action = messageData.action;

        if (action === 'new_token') {
            document.cookie = "access_token=" + messageData.token;
        } else if (action === 'message_deleted') {
            const messageId = messageData.message_id;
            const messageElement = document.querySelector(`.message-item[data-message-id="${String(messageId)}"]`);
            if (messageElement) {
                messageElement.remove();
                console.log(`Сообщение с ID: ${messageId} удалено`);
            } else {
                console.warn(`Message with id: ${messageId} not found for deletion`);
            }
        } else if (action === 'message_updated') {
            const messageId = messageData.message_id;
            const newMessageText = messageData.new_text;
            const newFileId = messageData.file_id;
            const newFileName = messageData.file_name;
            const editTimestamp = messageData.edit_timestamp;

            const messageElement = document.querySelector(`.message-item[data-message-id="${messageId}"]`);
            if (messageElement) {
                const messageContentElement = messageElement.querySelector('.message-content');

                // Очищаем текущее содержимое, но сохраняем выпадающее меню, если оно есть
                const dropdownMenu = messageElement.querySelector('.message-dropdown');
                messageContentElement.innerHTML = '';

                // Добавляем новый текст сообщения
                const newTextElement = document.createElement('div');
                newTextElement.textContent = newMessageText;
                messageContentElement.appendChild(newTextElement);

                // Если есть файл, добавляем ссылку на него
                if (newFileId && newFileName) {
                    const fileLink = document.createElement('a');
                    fileLink.href = `/files/${newFileId}`;
                    fileLink.textContent = newFileName;
                    messageContentElement.appendChild(fileLink);
                }

                // Добавляем метку об изменении
                const timeElement = document.createElement('div');
                timeElement.textContent = `Изменено: ${new Date(editTimestamp).toLocaleString()}`;
                messageContentElement.appendChild(timeElement);

                // Возвращаем выпадающее меню обратно в messageContentElement
                if (dropdownMenu) {
                    messageContentElement.appendChild(dropdownMenu);
                }
            }


        } else if (action === 'update_last_message') {
            const chatElement = document.querySelector(`.clickable-chat[data-chat-id="${messageData.chat_id}"]`);
            if (chatElement) {
                let lastMessageText = messageData.last_message;

                // Проверяем, содержит ли сообщение информацию о файле
                if (lastMessageText.includes('[[FILE]]')) {
                    const fileParts = lastMessageText.split('[[FILE]]')[1].split('[[/FILE]]')[0].split(', ');
                    const fileName = fileParts.find(part => part.startsWith('File Name')).split(': ')[1];
                    lastMessageText = fileName; // Используем только имя файла для отображения
                }

                // Обрезаем текст сообщения до 35 символов
                if (lastMessageText.length > 35) {
                    lastMessageText = lastMessageText.substring(0, 35) + '...';
                }

                let lastMessageElement = chatElement.querySelector('.last_message');
                if (lastMessageElement) {
                    lastMessageElement.textContent = `${messageData.sender_phone}: ${lastMessageText}`;
                } else {
                    lastMessageElement = document.createElement('p');
                    lastMessageElement.classList.add('last_message');
                    lastMessageElement.textContent = `${messageData.sender_phone}: ${lastMessageText}`;
                    chatElement.appendChild(lastMessageElement);
                }
            }
        } else if (messageData.message && messageData.sender_phone_number) {
            const messagesList = document.getElementById('chat-history');
            const newMessageItem = document.createElement('div');
            newMessageItem.className = "message-item";
            newMessageItem.dataset.messageId = messageData.message.id;

            if (messageData.sender_nickname === "{{ current_user.nickname }}") {
                newMessageItem.className += " user";
            }

            const messageContent = document.createElement('div');
            messageContent.className = 'message-content';
            const rawMessage = messageData.message;

            if (rawMessage.includes('[[FILE]]') && rawMessage.includes('[[/FILE]]')) {
                const [text, fileInfo] = rawMessage.split('[[FILE]]');
                const cleanedFileInfo = fileInfo.replace('[[/FILE]]', '');
                const [fileIdInfo, fileNameInfo] = cleanedFileInfo.split(', ');
                const fileId = fileIdInfo.split(': ')[1];
                const fileName = fileNameInfo.split(': ')[1];

                const messageTextElement = document.createElement('div');
                messageTextElement.innerText = text;
                messageContent.appendChild(messageTextElement);

                const fileLink = document.createElement('div');
                const fileAnchor = document.createElement('a');
                fileAnchor.href = `/files/${fileId}`;
                fileAnchor.innerText = fileName;
                fileLink.appendChild(fileAnchor);
                messageContent.appendChild(fileLink);
            } else {
                const messageTextElement = document.createElement('div');
                messageTextElement.innerText = rawMessage;
                messageContent.appendChild(messageTextElement);
            }

            const timeElement = document.createElement('div');
            timeElement.innerText = "Отправлено: " + (messageData.timestamp || "undefined");
            messageContent.appendChild(timeElement);

            const dropdown = document.createElement('div');
            dropdown.className = 'message-dropdown';
            const dropdownIcon = document.createElement('img');
            dropdownIcon.src = '/static/downarrow.png';
            dropdownIcon.alt = 'Options';
            dropdownIcon.className = 'message-options-icon';

            const currentUserPhoneNumber = "{{ current_user.phone_number }}";
            const isAdmin = chatOwnerId === currentUserPhoneNumber; // Предполагается, что chatOwnerId уже определен

            // Создание выпадающего меню
            const dropdownContent = document.createElement('div');
            dropdownContent.className = 'message-options';
            dropdownContent.style.display = 'none';

            // Показывать кнопку "Удалить сообщение" только если пользователь является администратором или автором сообщения
            if (isAdmin || messageData.sender_phone_number === currentUserPhoneNumber) {
                const deleteButton = document.createElement('button');
                deleteButton.className = 'dropdown-item';
                deleteButton.textContent = 'Удалить сообщение';
                deleteButton.onclick = function () {
                    const messageIdToDelete = newMessageItem.dataset.messageId;
                    ws.send(JSON.stringify({"action": "delete_message", "message_id": messageIdToDelete}));
                };
                dropdownContent.appendChild(deleteButton);
            }

            // Проверка на авторство сообщения для отображения кнопки "Редактировать"
            if (messageData.sender_phone_number === "{{ current_user.phone_number }}") {
                const editButton = document.createElement('button');
                editButton.className = 'dropdown-item edit-message-button';
                editButton.textContent = 'Редактировать';
                editButton.onclick = function () {
                    const messageIdToEdit = newMessageItem.dataset.messageId;
                    editChatMessage(messageIdToEdit);
                };
                dropdownContent.appendChild(editButton);
            }

            const forwardButton = document.createElement('button');
            forwardButton.className = 'dropdown-item';
            forwardButton.textContent = 'Переслать';
            dropdownContent.appendChild(forwardButton);

            dropdown.appendChild(dropdownIcon);
            dropdown.appendChild(dropdownContent);
            messageContent.appendChild(dropdown);
            newMessageItem.appendChild(messageContent);
            messagesList.appendChild(newMessageItem);
        } else {
            console.warn('Неожиданный формат сообщения: ', messageData);
        }
    };
    let chatOwnerId;

// Предполагается, что chatId уже определен
    fetchChatOwner(chatId)
        .then(ownerPhoneNumber => {
            chatOwnerId = ownerPhoneNumber;
            // Вы можете тут же обновить интерфейс или выполнить другие действия
        })
        .catch(error => console.error(error));

    async function fetchChatOwner(chatId) {
        try {
            const response = await fetch(`/api/chat/${chatId}/owner`);
            if (!response.ok) {
                throw new Error(`Error: ${response.statusText}`);
            }
            const data = await response.json();
            return data.owner_phone_number;
        } catch (error) {
            console.error('Ошибка при получении владельца чата:', error);
            return null;
        }
    }


    // Функция для открытия и закрытия "шторки"
    function toggleDrawer() {
        const drawer = document.getElementById('chatDrawer');
        if (drawer) {
            drawer.classList.toggle('open');
        }
    }


    // Обработчик для кнопки "Изменить фото"
    const changePhotoButton = document.getElementById('change-photo-button');
    const photoUploadInput = document.getElementById('photo-upload');
    if (changePhotoButton && photoUploadInput) {
        changePhotoButton.addEventListener('click', function () {
            photoUploadInput.click();
        });

        photoUploadInput.addEventListener('change', function () {
            if (this.files && this.files[0]) {
                const formData = new FormData();
                formData.append('new_picture', this.files[0]);

                fetch(`/chats/${chatId}/change_picture`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${access_token}`
                    },
                    body: formData
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'picture updated') {
                            const newSrc = `/chat/picture/${chatId}?${new Date().getTime()}`;

                            // Обновляем фото в "шторке"
                            const chatImage = document.getElementById('chatImage');
                            chatImage.setAttribute('src', newSrc);

                            // Обновляем фото в контейнере с названием чата
                            const interlocutorImage = document.querySelector('.interlocutor-info img');
                            if (interlocutorImage) {
                                interlocutorImage.setAttribute('src', newSrc);
                            }

                            // Обновляем фото в левой панели
                            const chatItemInLeftPanel = document.querySelector(`.clickable-chat[data-chat-id="${chatId}"] .profile-picture`);
                            if (chatItemInLeftPanel) {
                                chatItemInLeftPanel.setAttribute('src', newSrc);
                            }
                        }
                    })
                    .catch(error => console.error('Error:', error));
            }
        });
    }

    $(document).ready(function () {
        // Обработчик событий для открытия "шторки"
        const interlocutorInfo = document.querySelector('.interlocutor-info');
        if (interlocutorInfo) {
            interlocutorInfo.addEventListener('click', toggleDrawer);
        }

        // Обработчик для закрытия "шторки" при клике вне её области
        $(document).on('click', function (event) {
            if (!$(event.target).closest('#chatDrawer, .interlocutor-info').length) {
                if ($('#chatDrawer').hasClass('open')) {
                    toggleDrawer();
                }
            }
        });

        // Обработка отправки формы изменения названия чата
        $(document).on('submit', '.change-chat-name-form', function (e) {
            e.preventDefault();
            let form = $(this);
            let url = form.attr('action');
            let newNameInput = form.find('input[name="new_name"]');
            let newName = newNameInput.val();

            $.ajax({
                url: url,
                type: 'POST',
                data: {new_name: newName},
                success: function (response) {
                    if (response.status === 'success') {
                        // Обновляем название в шапке чата
                        $('.chat-name').text(response.new_name);

                        // Обновляем название в левой панели
                        $(`.clickable-chat[data-chat-id="${chatId}"] .username`).text(response.new_name);


                        // Очищаем поле ввода
                        newNameInput.val('');
                    } else {
                        alert('Ошибка при изменении названия чата');
                    }
                },
                error: function () {
                    alert('Ошибка при отправке запроса');
                }
            });
        });
    });
}


function addOption() {
    const newOption = document.createElement('input');
    newOption.type = 'text';
    newOption.name = 'options';
    newOption.placeholder = 'New poll option';
    document.getElementById('poll-options').appendChild(newOption);
}

function createPoll() {
    const question = document.getElementById("poll-question").value;
    const optionsNodes = document.getElementsByName("options");
    const options = Array.from(optionsNodes).map(node => node.value);
    if (question === '' || options.some(option => option === '')) {
        alert('Вопрос и варианты ответа не должны быть пустыми.');
        return;
    }
    const pollData = {
        "action": "create_poll",
        "question": question,
        "options": options,
        "creator_phone_number": "{{ current_user.phone_number }}"
    };
    ws.send(JSON.stringify(pollData));
}


// Инициализация кода для create_chat.html
function initializeCreateChatJS() {
    const createChatForm = document.querySelector('form[action="/create_chat"]');
    if (createChatForm) {
        createChatForm.addEventListener('submit', function (event) {
            event.preventDefault();
            const formData = new FormData(createChatForm);

            // Сбор данных из чекбоксов
            document.querySelectorAll('input[name="user_nicknames"]:checked').forEach((checkbox) => {
                formData.append('user_nicknames', checkbox.value);
            });

            fetch('/create_chat', {
                method: 'POST',
                body: formData
            })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'initialized') {
                        fetch('/create_chat_1')
                            .then(response => response.text())
                            .then(html => {
                                document.querySelector('#dialog-panel').innerHTML = html;
                                initializeCreateChatJS_1(data.users);  // Важно: инициализация скриптов для новой формы
                            })
                            .catch(error => {
                                console.error('Ошибка:', error);
                            });

                    } else {
                        console.log('Ошибка при создании чата:', data.error || "Unknown error");
                    }

                })
                .catch(error => {
                    console.error('Ошибка при отправке формы:', error);
                });
        });
    }
}

function initializeCreateChatJS_1(users) {
    console.log("initializeCreateChatJS is called"); // Отладка
    const createChatForm = document.querySelector('form[action="/create_chat"]');
    if (createChatForm) {
        createChatForm.addEventListener('submit', function (event) {
            event.preventDefault();
            const formData = new FormData(createChatForm);

            // Сбор данных из чекбоксов
            document.querySelectorAll('input[name="user_nicknames"]:checked').forEach((checkbox) => {
                formData.append('user_nicknames', checkbox.value);
            });
            formData.append('chat_users', users);

            fetch('/create_chat_1', {
                method: 'POST',
                body: formData,
            })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'created' && data.chat_id) {
                        fetch(`/chat/${data.chat_id}`)
                            .then(response => response.text())
                            .then(html => {
                                document.querySelector('#dialog-panel').innerHTML = html;
                                initializeChatJS(data.chat_id);
                            })
                            .catch(error => {
                                console.error('Ошибка:', error);
                            });
                    } else {
                        console.log('Ошибка при создании чата:', data.error || "Unknown error");
                    }

                })
                .catch(error => {
                    console.error('Ошибка при отправке формы:', error);
                });
        });
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Загрузка формы создания чата
    const createChatLink = document.querySelector('.create-chat-link');
    if (createChatLink) {
        createChatLink.addEventListener('click', function (event) {
            event.preventDefault();
            fetch('/create_chat')
                .then(response => response.text())
                .then(html => {
                    document.querySelector('#dialog-panel').innerHTML = html;
                    initializeCreateChatJS();  // Важно: инициализация скриптов для новой формы
                })
                .catch(error => {
                    console.error('Ошибка:', error);
                });
        });
    }
});

function changeImage() {
    var input = document.getElementById('chat_image');
    var preview = document.getElementById('previewImage');

    if (input.files && input.files[0]) {
        var reader = new FileReader();

        reader.onload = function (e) {
            preview.src = e.target.result;
        };

        reader.readAsDataURL(input.files[0]);
    } else {
        // Если файл не выбран, используйте изображение по умолчанию
        preview.src = '../static/default.svg';
    }
}

document.getElementById('chat_image').addEventListener('change', function () {
    var fileName = this.value.split('\\').pop();
    document.getElementById('selected_image').textContent = fileName;
});