🏥 DoveRx - Medical Social Network & Forum
🔗 Live Demo: https://doverx.vercel.app

DoveRx is a comprehensive medical social network platform that connects health-conscious users with medical professionals (Doctors, Medical Students). The system enables Q&A, knowledge sharing, online health consultations, and personal medical record management.

This repository contains the Full-stack source code for the project, including the Backend (Django) and Frontend (React.js).

🌐 System Overview
DoveRx operates on a decoupled Client-Server architecture:

Frontend: React.js (Single Page Application) providing a modern, optimized user experience, deployed on Vercel.

Backend: RESTful API built with Django Rest # 🏥 DoveRx - Medical Social Network & Forum

[![Live Demo](https://img.shields.io/badge/Live_Demo-doverx.vercel.app-2563eb?style=for-the-badge&logo=vercel)](https://doverx.vercel.app)

**🔗 Live Demo:** [**https://doverx.vercel.app**](https://doverx.vercel.app)

**DoveRx** is a comprehensive medical social network platform that connects health-conscious users with medical professionals (Doctors, Medical Students). The system enables Q&A, knowledge sharing, online health consultations, and personal medical record management.

This repository contains the **Full-stack** source code for the project, including the Backend (Django) and Frontend (**React.js**).

---

## 🌐 System Overview

DoveRx operates on a decoupled Client-Server architecture:

* **Frontend:** **React.js** (Single Page Application) providing a modern, optimized user experience, deployed on **Vercel**.
* **Backend:** RESTful API built with **Django Rest Framework**, deployed on **Railway**.
* **Database:** **Neon (PostgreSQL)** Serverless for high performance and scalability.
* **Real-time Engine:** **Redis** + **Django Channels** handling instant Chat and Notifications.
* **Media Storage:** **Cloudinary** for storage and optimization of images/videos.

---

## 🎨 UI/UX Highlights (React.js Frontend)

The React interface is designed for fluidity and instant feedback:

* **Optimistic UI:** Uses React State to update the interface (Like, Comment, Friend Requests) immediately before waiting for server confirmation.
* **Real-time Feedback:**
    * **Chat:** Real-time components update incoming messages, "typing..." indicators, and "seen" statuses via WebSocket.
    * **Notifications:** Notification dropdown updates instantly without page reloads.
* **Smart Components:**
    * **Debounce Search:** Search input uses debounce techniques to minimize request load.
    * **Dynamic Modals:** State-managed modals for creating posts, comments, and viewing media.
* **Media Handling:** Multi-threaded uploads with instant browser-side previews.

---

## 🚀 Extended Features (Technical Depth)

The project implements advanced Full-stack techniques:

1.  **Security & Auth:**
    * **React:** **Refresh Token Locking** mechanism in Axios Interceptors to handle expired tokens automatically and safely.
    * **Backend:** JWT Authentication, Server-side Google OAuth2 verification.
    * **WebSocket:** Custom Middleware for JWT authentication on socket connections.

2.  **Role-Based Access Control (RBAC):**
    * Strict separation between **User** and **Doctor** roles from Database to UI.
    * Specialized Doctor registration flow with email OTP verification.

3.  **Friendship & Social Graph:**
    * Complex status management: *Pending, Accepted, Rejected, Blocked*.
    * Friend request processing directly via the Navbar dropdown.

---

## 🛠️ Technology & Libraries

### Frontend (React Ecosystem)
* **Core:** React.js (Hooks, Context API).
* **Routing:** React Router DOM (v6).
* **HTTP Client:** Axios (Custom Instance & Interceptors).
* **Real-time:** Native WebSocket API (Custom Services wrapper).
* **UI/UX:** CSS Modules, React-Toastify, React-Easy-Crop (avatar processing).

### Backend (Django Ecosystem)
* **Core:** Python, Django, Django REST Framework.
* **Real-time:** Django Channels, Daphne.
* **Database:** PostgreSQL (Neon), Redis.
* **Storage:** Cloudinary.

---

## 📂 Project Structure

Monorepo Structure:

```bash
DOVERX/
├── Backend/                # Django Project
│   ├── accounts/           # Auth, User, Profile, Friend logic
│   ├── chat/               # WebSocket Chat logic
│   ├── social/             # Post, Feed, Comment logic
│   ├── doverx_backend/     # Config (Settings, ASGI)
│   └── manage.py
│
└── Frontend/               # React.js Project
    ├── public/
    ├── src/
    │   ├── api/            # Axios config (api.js, posts.js)
    │   ├── components/     # React Components (Navbar, ChatPopup, PostCard...)
    │   ├── pages/          # Pages (Dashboard, Login, Profile...)
    │   ├── services/       # WebSocket Services (chatWebSocket.js...)
    │   └── utils/          # Helpers (imageHelper, timeUtils...)
    └── package.json

✅ Requirements
Node.js: v16+ (Required for React dev server).

Python: v3.10+

Redis: (Required for Chat/Real-time features).

PostgreSQL.

💻 Installation & Run
1. Setup Backend (Django)
cd Backend
python -m venv venv
# Activate venv (Windows: venv\Scripts\activate | Mac/Linux: source venv/bin/activate)

pip install -r requirements.txt
# Configure .env file (DB, Redis, Cloudinary...)

python manage.py migrate
python manage.py runserver
2. Setup Frontend (React.js)
cd Frontend
# Install dependencies
npm install

# Configure .env file (REACT_APP_API_BASE=http://localhost:8000)

# Start Development Server
npm start
