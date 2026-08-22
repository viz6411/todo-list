/**
 * Todo List Frontend Application
 * Interacts with the backend API at /api/todos
 */

(function() {
    'use strict';

    const API_BASE = '/api/todos';
    let todos = [];
    let currentFilter = 'all';

    // DOM Elements
    const addForm = document.getElementById('add-form');
    const todoInput = document.getElementById('todo-input');
    const todoList = document.getElementById('todo-list');
    const summary = document.getElementById('summary');
    const errorMsg = document.getElementById('error-msg');
    const filterBtns = document.querySelectorAll('.filter-btn');

    /**
     * Fetch all todos from the API
     */
    async function fetchTodos() {
        try {
            const response = await fetch(API_BASE);
            if (!response.ok) {
                showError(`Failed to fetch todos: ${response.status}`);
                return;
            }
            todos = await response.json();
            render();
        } catch (err) {
            showError('Network error: ' + err.message);
        }
    }

    /**
     * Add a new todo
     */
    async function addTodo(title) {
        if (!title.trim()) return;

        try {
            const response = await fetch(API_BASE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: title.trim() })
            });

            if (!response.ok) {
                const data = await response.json();
                showError(data.error || 'Failed to add todo');
                return;
            }

            const todo = await response.json();
            todos.push(todo);
            render();
            todoInput.value = '';
            hideError();
        } catch (err) {
            showError('Network error: ' + err.message);
        }
    }

    /**
     * Toggle todo completion status
     */
    async function toggleTodo(todoId) {
        const todo = todos.find(t => t.id === todoId);
        if (!todo) return;

        try {
            const response = await fetch(`${API_BASE}/${todoId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ completed: !todo.completed })
            });

            if (!response.ok) {
                showError('Failed to update todo');
                return;
            }

            const updated = await response.json();
            todo.completed = updated.completed;
            render();
            hideError();
        } catch (err) {
            showError('Network error: ' + err.message);
        }
    }

    /**
     * Delete a todo
     */
    async function deleteTodo(todoId) {
        try {
            const response = await fetch(`${API_BASE}/${todoId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                showError('Failed to delete todo');
                return;
            }

            todos = todos.filter(t => t.id !== todoId);
            render();
            hideError();
        } catch (err) {
            showError('Network error: ' + err.message);
        }
    }

    /**
     * Filter todos based on current filter setting
     */
    function getFilteredTodos() {
        switch (currentFilter) {
            case 'active':
                return todos.filter(t => !t.completed);
            case 'completed':
                return todos.filter(t => t.completed);
            default:
                return todos;
        }
    }

    /**
     * Render the todo list and summary
     */
    function render() {
        const filtered = getFilteredTodos();

        // Build list items
        todoList.innerHTML = '';
        filtered.forEach(todo => {
            const li = document.createElement('li');
            li.className = 'todo-item' + (todo.completed ? ' completed' : '');

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = todo.completed;
            checkbox.addEventListener('change', () => toggleTodo(todo.id));

            const span = document.createElement('span');
            span.className = 'todo-title';
            span.textContent = todo.title;
            span.addEventListener('click', () => toggleTodo(todo.id));

            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-btn';
            deleteBtn.textContent = '×';
            deleteBtn.addEventListener('click', () => deleteTodo(todo.id));

            li.appendChild(checkbox);
            li.appendChild(span);
            li.appendChild(deleteBtn);
            todoList.appendChild(li);
        });

        // Update summary
        const activeCount = todos.filter(t => !t.completed).length;
        const totalCount = todos.length;
        summary.textContent = `${activeCount} item${activeCount !== 1 ? 's' : ''} left · ${totalCount} total`;
    }

    /**
     * Show error message
     */
    function showError(msg) {
        errorMsg.textContent = msg;
        errorMsg.style.display = 'block';
    }

    /**
     * Hide error message
     */
    function hideError() {
        errorMsg.textContent = '';
        errorMsg.style.display = 'none';
    }

    // Event listeners
    addForm.addEventListener('submit', (e) => {
        e.preventDefault();
        addTodo(todoInput.value);
    });

    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.filter;
            render();
        });
    });

    // Initialize
    fetchTodos();
})();
