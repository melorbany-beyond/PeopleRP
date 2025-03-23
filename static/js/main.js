// Project Modal Functions
function openProjectModal() {
    document.getElementById('projectModal').classList.remove('hidden');
    document.getElementById('modalTitle').textContent = 'Add Project';
    document.getElementById('projectForm').reset();
    document.getElementById('projectId').value = '';
}

function closeProjectModal() {
    document.getElementById('projectModal').classList.add('hidden');
}

function editProject(project) {
    document.getElementById('projectModal').classList.remove('hidden');
    document.getElementById('modalTitle').textContent = 'Edit Project';
    
    document.getElementById('projectId').value = project.id;
    document.getElementById('name').value = project.name;
    document.getElementById('project_type').value = project.project_type;
    document.getElementById('status').value = project.status;
    document.getElementById('start_date').value = project.start_date;
    document.getElementById('end_date').value = project.end_date;
}

async function deleteProject(projectId) {
    if (confirm('Are you sure you want to delete this project?')) {
        try {
            const response = await fetch(`/projects/${projectId}`, {
                method: 'DELETE',
            });
            if (response.ok) {
                window.location.reload();
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }
}

async function handleProjectSubmit(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const projectId = formData.get('id');
    
    const data = {
        name: formData.get('name'),
        project_type: formData.get('project_type'),
        status: formData.get('status'),
        start_date: formData.get('start_date'),
        end_date: formData.get('end_date')
    };

    try {
        const url = projectId ? `/projects/${projectId}` : '/projects';
        const method = projectId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (response.ok) {
            window.location.reload();
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

// People Modal Functions
function openPersonModal() {
    document.getElementById('personModal').classList.remove('hidden');
    document.getElementById('modalTitle').textContent = 'Add Person';
    document.getElementById('personForm').reset();
    document.getElementById('personId').value = '';
}

function closePersonModal() {
    document.getElementById('personModal').classList.add('hidden');
}

function editPerson(person) {
    document.getElementById('personModal').classList.remove('hidden');
    document.getElementById('modalTitle').textContent = 'Edit Person';
    
    document.getElementById('personId').value = person.id;
    document.getElementById('name').value = person.name;
    document.getElementById('role').value = person.role;
    document.getElementById('availability').value = person.availability;
}

async function deletePerson(personId) {
    if (confirm('Are you sure you want to delete this person?')) {
        try {
            const response = await fetch(`/people/${personId}`, {
                method: 'DELETE',
            });
            if (response.ok) {
                window.location.reload();
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }
}

async function handlePersonSubmit(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const personId = formData.get('id');
    
    const data = {
        name: formData.get('name'),
        role: formData.get('role'),
        availability: formData.get('availability')
    };

    try {
        const url = personId ? `/people/${personId}` : '/people';
        const method = personId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (response.ok) {
            window.location.reload();
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

// Assignment Modal Functions
function openAssignmentModal() {
    document.getElementById('assignmentModal').classList.remove('hidden');
    document.getElementById('modalTitle').textContent = 'Add Team Member';
    document.getElementById('assignmentForm').reset();
    document.getElementById('assignmentId').value = '';
}

function closeAssignmentModal() {
    document.getElementById('assignmentModal').classList.add('hidden');
}

function editAssignment(assignment) {
    document.getElementById('assignmentModal').classList.remove('hidden');
    document.getElementById('modalTitle').textContent = 'Edit Assignment';
    
    document.getElementById('assignmentId').value = assignment.id;
    document.getElementById('person_id').value = assignment.person_id;
    document.getElementById('allocation').value = assignment.allocation;
    document.getElementById('start_date').value = assignment.start_date;
    document.getElementById('end_date').value = assignment.end_date;
}

async function deleteAssignment(assignmentId) {
    if (confirm('Are you sure you want to remove this team member from the project?')) {
        try {
            const projectId = window.location.pathname.split('/').pop();
            const response = await fetch(`/assignments/${projectId}/${assignmentId}`, {
                method: 'DELETE',
            });
            if (response.ok) {
                window.location.reload();
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }
}

async function handleAssignmentSubmit(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const assignmentId = formData.get('id');
    const projectId = window.location.pathname.split('/').pop();
    
    const data = {
        person_id: formData.get('person_id'),
        allocation: formData.get('allocation'),
        start_date: formData.get('start_date'),
        end_date: formData.get('end_date')
    };

    try {
        const url = assignmentId ? 
            `/assignments/${projectId}/${assignmentId}` : 
            `/assignments/${projectId}`;
        const method = assignmentId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (response.ok) {
            window.location.reload();
        } else {
            const errorData = await response.json();
            alert(errorData.error || 'An error occurred');
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

// User Modal Functions
function openUserModal() {
    const modal = document.getElementById('userModal');
    modal.classList.remove('hidden');
    document.getElementById('userForm').reset();
}

function closeUserModal() {
    const modal = document.getElementById('userModal');
    modal.classList.add('hidden');
    document.getElementById('userForm').reset();
}

// Handle user form submission
document.addEventListener('DOMContentLoaded', function() {
    const userForm = document.getElementById('userForm');
    if (userForm) {
        userForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = {
                name: document.getElementById('name').value,
                email: document.getElementById('email').value,
                role: document.getElementById('role')?.value || 'Normal'
            };

            try {
                const response = await fetch('/auth/invite', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(formData)
                });

                const data = await response.json();

                if (response.ok) {
                    alert('User invited successfully!');
                    window.location.reload();
                } else {
                    alert(data.error || 'Failed to invite user');
                }
            } catch (error) {
                alert('An error occurred while inviting the user');
            }

            closeUserModal();
        });
    }
});

// Handle user status toggle
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.toggle-status-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const userId = btn.dataset.userId;
            const currentStatus = btn.dataset.currentStatus === 'True';
            
            try {
                const response = await fetch(`/api/users/${userId}/status`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        is_active: !currentStatus
                    })
                });

                const data = await response.json();

                if (response.ok) {
                    window.location.reload();
                } else {
                    alert(data.error || 'Failed to update user status');
                }
            } catch (error) {
                alert('An error occurred while updating user status');
            }
        });
    });
}); 