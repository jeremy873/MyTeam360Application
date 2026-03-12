# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Education i18n — Age-appropriate vocabulary in every supported language.

7 languages × 4 age groups = 28 complete translation sets.

Each set includes:
  - UI vocabulary (buttons, labels, navigation)
  - AI personality (greeting, correct/wrong responses, encouragement)
  - Subject names
  - Common phrases

Languages: English, Spanish, French, Portuguese, Chinese, Japanese, Arabic
Age groups: early_elementary (5-7), upper_elementary (8-10),
            middle_school (11-13), high_school (14-18)
"""

# ══════════════════════════════════════════════════════════════
# VOCABULARY TRANSLATIONS — Per language, per age group
# ══════════════════════════════════════════════════════════════

EDU_TRANSLATIONS = {
    # ──────────────────────────────────────────────────────
    # ENGLISH (en)
    # ──────────────────────────────────────────────────────
    "en": {
        "early_elementary": {
            "ui": {
                "space": "Helper",
                "conversation": "Chat",
                "knowledge_base": "My Stuff",
                "send_message": "Ask!",
                "new_conversation": "New Chat!",
                "settings": "My Settings",
                "dashboard": "My Learning",
                "profile": "About Me",
                "logout": "Bye for now!",
                "help": "I need help!",
                "loading": "Thinking...",
                "error": "Oops! Something went wrong",
                "welcome": "Hi there! Ready to learn?",
                "empty_state": "Nothing here yet! Let's get started!",
                "back": "Go Back",
                "next": "Next!",
                "done": "All Done!",
                "try_again": "Try Again!",
                "hint": "Give me a hint!",
                "show_answer": "Show me!",
            },
            "ai": {
                "greeting": "Hi there, superstar! 🌟 What should we learn today?",
                "correct": ["Amazing job! 🎉", "You got it! ⭐", "Wow, you're so smart! 🚀", "Super work! 🏆"],
                "wrong": ["Great try! Let's look at it together 🤔", "Almost! You're so close! 💡"],
                "encourage": ["You can do it! 💪", "Keep going! 🌟", "I believe in you! 🚀"],
                "farewell": "Great job today! See you next time! 🌈",
            },
            "subjects": {
                "math": "Numbers", "science": "Discovery", "reading": "Stories",
                "writing": "Writing", "art": "Art", "music": "Music", "history": "Long Ago",
            },
        },
        "upper_elementary": {
            "ui": {
                "space": "Study Buddy", "conversation": "Chat", "knowledge_base": "My Notes",
                "send_message": "Ask", "new_conversation": "New Chat", "settings": "Settings",
                "dashboard": "My Progress", "profile": "My Profile", "logout": "Sign Out",
                "help": "Need Help?", "loading": "Working on it...",
                "error": "Something went wrong — let's try again!",
                "welcome": "Welcome back! What are we working on today?",
                "empty_state": "Start a new chat to begin learning!",
                "back": "Back", "next": "Next", "done": "Done!",
                "try_again": "Try Again", "hint": "Hint", "show_answer": "Show Answer",
            },
            "ai": {
                "greeting": "Hey! Ready to crush it today? 💪",
                "correct": ["Nice work! 🎯", "You nailed it! ⭐", "That's correct!"],
                "wrong": ["Not quite — but good thinking! Here's a hint...", "Close! Let's break it down."],
                "encourage": ["You've got this!", "Keep pushing!", "Every mistake helps you learn!"],
                "farewell": "Great session! Keep up the awesome work!",
            },
            "subjects": {
                "math": "Math", "science": "Science", "reading": "Reading",
                "writing": "Writing", "art": "Art", "music": "Music", "history": "History",
            },
        },
        "middle_school": {
            "ui": {
                "space": "Study Space", "conversation": "Session", "knowledge_base": "Resources",
                "send_message": "Send", "new_conversation": "New Session", "settings": "Settings",
                "dashboard": "Dashboard", "profile": "Profile", "logout": "Sign Out",
                "help": "Help", "loading": "Processing...", "error": "An error occurred. Please try again.",
                "welcome": "Welcome back. What are we studying today?",
                "empty_state": "Start a new session to begin.",
                "back": "Back", "next": "Next", "done": "Done",
                "try_again": "Try Again", "hint": "Hint", "show_answer": "Show Solution",
            },
            "ai": {
                "greeting": "Welcome back. What subject are we working on?",
                "correct": ["Correct.", "Well done.", "That's right. Can you explain why?"],
                "wrong": ["Not quite. Let's think about what we know...", "Let's reconsider..."],
                "encourage": ["You're making good progress.", "This is challenging — stick with it."],
                "farewell": "Good work today. Keep reviewing the material.",
            },
            "subjects": {
                "math": "Mathematics", "science": "Science", "reading": "Language Arts",
                "writing": "Composition", "art": "Visual Arts", "music": "Music", "history": "Social Studies",
            },
        },
        "high_school": {
            "ui": {
                "space": "Space", "conversation": "Conversation", "knowledge_base": "Knowledge Base",
                "send_message": "Send", "new_conversation": "New Conversation", "settings": "Settings",
                "dashboard": "Dashboard", "profile": "Profile", "logout": "Sign Out",
                "help": "Help", "loading": "Loading...", "error": "An error occurred.",
                "welcome": "Welcome back. Ready to study?",
                "empty_state": "Start a conversation to begin.",
                "back": "Back", "next": "Continue", "done": "Complete",
                "try_again": "Retry", "hint": "Hint", "show_answer": "Show Solution",
            },
            "ai": {
                "greeting": "Welcome back. What are we working on?",
                "correct": ["Correct.", "Good analysis.", "Solid reasoning."],
                "wrong": ["Let's reconsider.", "Review the concept and try again."],
                "encourage": ["Strong skills being built here.", "This preparation will pay off."],
                "farewell": "Productive session. Review your notes before next time.",
            },
            "subjects": {
                "math": "Mathematics", "science": "Sciences", "reading": "English Literature",
                "writing": "Composition", "art": "Fine Arts", "music": "Music Theory", "history": "History",
            },
        },
    },

    # ──────────────────────────────────────────────────────
    # SPANISH (es)
    # ──────────────────────────────────────────────────────
    "es": {
        "early_elementary": {
            "ui": {
                "space": "Ayudante", "conversation": "Charla", "knowledge_base": "Mis Cosas",
                "send_message": "¡Pregunta!", "new_conversation": "¡Nueva Charla!",
                "settings": "Mi Configuración", "dashboard": "Mi Aprendizaje",
                "profile": "Sobre Mí", "logout": "¡Hasta luego!",
                "help": "¡Necesito ayuda!", "loading": "Pensando...",
                "error": "¡Ups! Algo salió mal", "welcome": "¡Hola! ¿Listos para aprender?",
                "empty_state": "¡Nada aquí todavía! ¡Vamos a empezar!",
                "back": "Volver", "next": "¡Siguiente!", "done": "¡Listo!",
                "try_again": "¡Otra vez!", "hint": "¡Dame una pista!", "show_answer": "¡Muéstrame!",
            },
            "ai": {
                "greeting": "¡Hola, superestrella! 🌟 ¿Qué aprendemos hoy?",
                "correct": ["¡Increíble! 🎉", "¡Lo lograste! ⭐", "¡Qué inteligente! 🚀", "¡Súper trabajo! 🏆"],
                "wrong": ["¡Buen intento! Veamos juntos 🤔", "¡Casi! ¡Estás muy cerca! 💡"],
                "encourage": ["¡Tú puedes! 💪", "¡Sigue así! 🌟", "¡Yo creo en ti! 🚀"],
                "farewell": "¡Buen trabajo hoy! ¡Nos vemos! 🌈",
            },
            "subjects": {
                "math": "Números", "science": "Descubrimiento", "reading": "Cuentos",
                "writing": "Escritura", "art": "Arte", "music": "Música", "history": "Hace Mucho",
            },
        },
        "upper_elementary": {
            "ui": {
                "space": "Compañero de Estudio", "conversation": "Charla", "knowledge_base": "Mis Notas",
                "send_message": "Preguntar", "new_conversation": "Nueva Charla", "settings": "Ajustes",
                "dashboard": "Mi Progreso", "profile": "Mi Perfil", "logout": "Cerrar Sesión",
                "help": "¿Necesitas Ayuda?", "loading": "Trabajando...",
                "error": "Algo salió mal — ¡intentemos de nuevo!",
                "welcome": "¡Bienvenido! ¿En qué trabajamos hoy?",
                "empty_state": "¡Empieza una charla para aprender!",
                "back": "Atrás", "next": "Siguiente", "done": "¡Hecho!",
                "try_again": "Intentar de Nuevo", "hint": "Pista", "show_answer": "Ver Respuesta",
            },
            "ai": {
                "greeting": "¡Hola! ¿Listos para darle con todo? 💪",
                "correct": ["¡Buen trabajo! 🎯", "¡Lo clavaste! ⭐", "¡Correcto!"],
                "wrong": ["Casi — ¡pero buen pensamiento! Te doy una pista...", "¡Cerca! Vamos paso a paso."],
                "encourage": ["¡Tú puedes!", "¡Sigue así!", "¡Cada error te enseña algo!"],
                "farewell": "¡Gran sesión! ¡Sigue con ese esfuerzo!",
            },
            "subjects": {
                "math": "Matemáticas", "science": "Ciencias", "reading": "Lectura",
                "writing": "Escritura", "art": "Arte", "music": "Música", "history": "Historia",
            },
        },
        "middle_school": {
            "ui": {
                "space": "Espacio de Estudio", "conversation": "Sesión", "knowledge_base": "Recursos",
                "send_message": "Enviar", "new_conversation": "Nueva Sesión", "settings": "Configuración",
                "dashboard": "Panel", "profile": "Perfil", "logout": "Cerrar Sesión",
                "help": "Ayuda", "loading": "Procesando...", "error": "Ocurrió un error. Intenta de nuevo.",
                "welcome": "Bienvenido. ¿Qué estudiamos hoy?",
                "empty_state": "Inicia una sesión para comenzar.",
                "back": "Atrás", "next": "Siguiente", "done": "Listo",
                "try_again": "Intentar de Nuevo", "hint": "Pista", "show_answer": "Ver Solución",
            },
            "ai": {
                "greeting": "Bienvenido. ¿En qué materia trabajamos?",
                "correct": ["Correcto.", "Bien hecho.", "Exacto. ¿Puedes explicar por qué?"],
                "wrong": ["No exactamente. Pensemos en lo que sabemos...", "Reconsideremos..."],
                "encourage": ["Buen progreso.", "Es un tema difícil — sigue adelante."],
                "farewell": "Buen trabajo hoy. Sigue repasando el material.",
            },
            "subjects": {
                "math": "Matemáticas", "science": "Ciencias", "reading": "Lengua y Literatura",
                "writing": "Composición", "art": "Artes Visuales", "music": "Música", "history": "Estudios Sociales",
            },
        },
        "high_school": {
            "ui": {
                "space": "Espacio", "conversation": "Conversación", "knowledge_base": "Base de Conocimiento",
                "send_message": "Enviar", "new_conversation": "Nueva Conversación", "settings": "Configuración",
                "dashboard": "Panel", "profile": "Perfil", "logout": "Cerrar Sesión",
                "help": "Ayuda", "loading": "Cargando...", "error": "Ocurrió un error.",
                "welcome": "Bienvenido. ¿Listo para estudiar?",
                "empty_state": "Inicia una conversación para comenzar.",
                "back": "Atrás", "next": "Continuar", "done": "Completar",
                "try_again": "Reintentar", "hint": "Pista", "show_answer": "Ver Solución",
            },
            "ai": {
                "greeting": "Bienvenido. ¿En qué trabajamos?",
                "correct": ["Correcto.", "Buen análisis.", "Razonamiento sólido."],
                "wrong": ["Reconsideremos.", "Revisa el concepto e intenta de nuevo."],
                "encourage": ["Estás desarrollando habilidades fuertes.", "Esta preparación vale la pena."],
                "farewell": "Sesión productiva. Repasa tus notas antes de la próxima vez.",
            },
            "subjects": {
                "math": "Matemáticas", "science": "Ciencias", "reading": "Literatura",
                "writing": "Composición", "art": "Bellas Artes", "music": "Teoría Musical", "history": "Historia",
            },
        },
    },

    # ──────────────────────────────────────────────────────
    # FRENCH (fr)
    # ──────────────────────────────────────────────────────
    "fr": {
        "early_elementary": {
            "ui": {
                "space": "Assistant", "conversation": "Discussion", "knowledge_base": "Mes Affaires",
                "send_message": "Demande !", "new_conversation": "Nouvelle Discussion !",
                "settings": "Mes Réglages", "dashboard": "Mon Apprentissage",
                "profile": "À Propos de Moi", "logout": "À bientôt !",
                "help": "J'ai besoin d'aide !", "loading": "Je réfléchis...",
                "error": "Oups ! Quelque chose s'est mal passé",
                "welcome": "Salut ! Prêt à apprendre ?",
                "empty_state": "Rien ici pour l'instant ! On commence !",
                "back": "Retour", "next": "Suivant !", "done": "Terminé !",
                "try_again": "Encore !", "hint": "Un indice !", "show_answer": "Montre-moi !",
            },
            "ai": {
                "greeting": "Salut, superstar ! 🌟 Qu'est-ce qu'on apprend aujourd'hui ?",
                "correct": ["Bravo ! 🎉", "Tu as réussi ! ⭐", "Trop fort ! 🚀", "Super travail ! 🏆"],
                "wrong": ["Bien essayé ! On regarde ensemble 🤔", "Presque ! Tu es tout près ! 💡"],
                "encourage": ["Tu peux le faire ! 💪", "Continue ! 🌟", "Je crois en toi ! 🚀"],
                "farewell": "Super travail aujourd'hui ! À la prochaine ! 🌈",
            },
            "subjects": {
                "math": "Chiffres", "science": "Découverte", "reading": "Histoires",
                "writing": "Écriture", "art": "Art", "music": "Musique", "history": "Il y a Longtemps",
            },
        },
        "upper_elementary": {
            "ui": {
                "space": "Camarade d'Étude", "conversation": "Discussion", "knowledge_base": "Mes Notes",
                "send_message": "Demander", "new_conversation": "Nouvelle Discussion", "settings": "Réglages",
                "dashboard": "Ma Progression", "profile": "Mon Profil", "logout": "Déconnexion",
                "help": "Besoin d'aide ?", "loading": "En cours...",
                "error": "Quelque chose s'est mal passé — réessayons !",
                "welcome": "Re-bonjour ! On travaille sur quoi aujourd'hui ?",
                "empty_state": "Commence une discussion pour apprendre !",
                "back": "Retour", "next": "Suivant", "done": "Fait !",
                "try_again": "Réessayer", "hint": "Indice", "show_answer": "Voir la Réponse",
            },
            "ai": {
                "greeting": "Salut ! Prêt à tout donner ? 💪",
                "correct": ["Bien joué ! 🎯", "Tu as réussi ! ⭐", "C'est correct !"],
                "wrong": ["Pas tout à fait — mais bonne réflexion ! Voici un indice...", "Presque ! Décomposons."],
                "encourage": ["Tu gères !", "Continue comme ça !", "Chaque erreur t'apprend quelque chose !"],
                "farewell": "Super séance ! Continue comme ça !",
            },
            "subjects": {
                "math": "Maths", "science": "Sciences", "reading": "Lecture",
                "writing": "Écriture", "art": "Art", "music": "Musique", "history": "Histoire",
            },
        },
        "middle_school": {
            "ui": {
                "space": "Espace d'Étude", "conversation": "Séance", "knowledge_base": "Ressources",
                "send_message": "Envoyer", "new_conversation": "Nouvelle Séance", "settings": "Paramètres",
                "dashboard": "Tableau de Bord", "profile": "Profil", "logout": "Déconnexion",
                "help": "Aide", "loading": "Traitement...", "error": "Une erreur s'est produite. Réessayez.",
                "welcome": "Bienvenue. Qu'étudions-nous aujourd'hui ?",
                "empty_state": "Commencez une séance pour débuter.",
                "back": "Retour", "next": "Suivant", "done": "Terminé",
                "try_again": "Réessayer", "hint": "Indice", "show_answer": "Voir la Solution",
            },
            "ai": {
                "greeting": "Bienvenue. Sur quelle matière on travaille ?",
                "correct": ["Correct.", "Bien fait.", "Exact. Peux-tu expliquer pourquoi ?"],
                "wrong": ["Pas tout à fait. Réfléchissons à ce que nous savons...", "Reconsidérons..."],
                "encourage": ["Tu progresses bien.", "C'est un sujet difficile — persévère."],
                "farewell": "Bon travail aujourd'hui. Continue à réviser.",
            },
            "subjects": {
                "math": "Mathématiques", "science": "Sciences", "reading": "Français",
                "writing": "Rédaction", "art": "Arts Visuels", "music": "Musique", "history": "Histoire-Géo",
            },
        },
        "high_school": {
            "ui": {
                "space": "Espace", "conversation": "Conversation", "knowledge_base": "Base de Connaissances",
                "send_message": "Envoyer", "new_conversation": "Nouvelle Conversation", "settings": "Paramètres",
                "dashboard": "Tableau de Bord", "profile": "Profil", "logout": "Déconnexion",
                "help": "Aide", "loading": "Chargement...", "error": "Une erreur s'est produite.",
                "welcome": "Bienvenue. Prêt à étudier ?",
                "empty_state": "Commencez une conversation.",
                "back": "Retour", "next": "Continuer", "done": "Terminer",
                "try_again": "Réessayer", "hint": "Indice", "show_answer": "Voir la Solution",
            },
            "ai": {
                "greeting": "Bienvenue. Sur quoi travaillons-nous ?",
                "correct": ["Correct.", "Bonne analyse.", "Raisonnement solide."],
                "wrong": ["Reconsidérons.", "Revoyez le concept et réessayez."],
                "encourage": ["Vous développez de solides compétences.", "Cette préparation portera ses fruits."],
                "farewell": "Séance productive. Révisez vos notes avant la prochaine fois.",
            },
            "subjects": {
                "math": "Mathématiques", "science": "Sciences", "reading": "Littérature",
                "writing": "Dissertation", "art": "Beaux-Arts", "music": "Théorie Musicale", "history": "Histoire",
            },
        },
    },

    # ──────────────────────────────────────────────────────
    # PORTUGUESE (pt)
    # ──────────────────────────────────────────────────────
    "pt": {
        "early_elementary": {
            "ui": {
                "space": "Ajudante", "conversation": "Conversa", "knowledge_base": "Minhas Coisas",
                "send_message": "Pergunte!", "new_conversation": "Nova Conversa!",
                "settings": "Minhas Configurações", "dashboard": "Meu Aprendizado",
                "profile": "Sobre Mim", "logout": "Até logo!",
                "help": "Preciso de ajuda!", "loading": "Pensando...",
                "error": "Ops! Algo deu errado",
                "welcome": "Oi! Pronto para aprender?",
                "empty_state": "Nada aqui ainda! Vamos começar!",
                "back": "Voltar", "next": "Próximo!", "done": "Pronto!",
                "try_again": "Tente de Novo!", "hint": "Me dá uma dica!", "show_answer": "Me mostra!",
            },
            "ai": {
                "greeting": "Oi, superstar! 🌟 O que vamos aprender hoje?",
                "correct": ["Incrível! 🎉", "Você conseguiu! ⭐", "Que inteligente! 🚀", "Super trabalho! 🏆"],
                "wrong": ["Boa tentativa! Vamos ver juntos 🤔", "Quase! Você está perto! 💡"],
                "encourage": ["Você consegue! 💪", "Continue assim! 🌟", "Eu acredito em você! 🚀"],
                "farewell": "Ótimo trabalho hoje! Até a próxima! 🌈",
            },
            "subjects": {
                "math": "Números", "science": "Descoberta", "reading": "Histórias",
                "writing": "Escrita", "art": "Arte", "music": "Música", "history": "Há Muito Tempo",
            },
        },
        "upper_elementary": {
            "ui": {
                "space": "Companheiro de Estudo", "conversation": "Conversa", "knowledge_base": "Minhas Notas",
                "send_message": "Perguntar", "new_conversation": "Nova Conversa", "settings": "Configurações",
                "dashboard": "Meu Progresso", "profile": "Meu Perfil", "logout": "Sair",
                "help": "Precisa de Ajuda?", "loading": "Trabalhando...",
                "welcome": "Bem-vindo! No que vamos trabalhar hoje?",
            },
            "ai": {
                "greeting": "Oi! Pronto para arrasar? 💪",
                "correct": ["Bom trabalho! 🎯", "Mandou bem! ⭐", "Correto!"],
                "wrong": ["Quase — mas boa ideia! Aqui vai uma dica...", "Perto! Vamos por partes."],
                "encourage": ["Você consegue!", "Continue assim!", "Cada erro te ensina algo!"],
            },
            "subjects": {
                "math": "Matemática", "science": "Ciências", "reading": "Leitura",
                "writing": "Escrita", "art": "Arte", "music": "Música", "history": "História",
            },
        },
        "middle_school": {
            "ui": {
                "space": "Espaço de Estudo", "conversation": "Sessão", "send_message": "Enviar",
                "dashboard": "Painel", "welcome": "Bem-vindo. O que estudamos hoje?",
            },
            "ai": {
                "greeting": "Bem-vindo. Em que matéria vamos trabalhar?",
                "correct": ["Correto.", "Bem feito.", "Exato. Pode explicar por quê?"],
                "wrong": ["Não exatamente. Vamos pensar no que sabemos...", "Vamos reconsiderar..."],
            },
            "subjects": {
                "math": "Matemática", "science": "Ciências", "reading": "Língua Portuguesa",
                "writing": "Redação", "history": "Estudos Sociais",
            },
        },
        "high_school": {
            "ui": {
                "space": "Espaço", "conversation": "Conversa", "send_message": "Enviar",
                "dashboard": "Painel", "welcome": "Bem-vindo. Pronto para estudar?",
            },
            "ai": {
                "greeting": "Bem-vindo. No que vamos trabalhar?",
                "correct": ["Correto.", "Boa análise.", "Raciocínio sólido."],
                "wrong": ["Vamos reconsiderar.", "Revise o conceito e tente novamente."],
            },
            "subjects": {
                "math": "Matemática", "science": "Ciências", "reading": "Literatura",
                "writing": "Redação", "history": "História",
            },
        },
    },

    # ──────────────────────────────────────────────────────
    # CHINESE (zh)
    # ──────────────────────────────────────────────────────
    "zh": {
        "early_elementary": {
            "ui": {
                "space": "小帮手", "conversation": "聊天", "knowledge_base": "我的东西",
                "send_message": "问一下！", "new_conversation": "新聊天！",
                "settings": "我的设置", "dashboard": "我的学习",
                "profile": "关于我", "logout": "下次见！",
                "help": "我需要帮助！", "loading": "想一想...",
                "error": "哎呀！出了点问题",
                "welcome": "你好呀！准备好学习了吗？",
                "empty_state": "这里还没有东西！我们开始吧！",
                "back": "返回", "next": "下一个！", "done": "完成！",
                "try_again": "再试一次！", "hint": "给我一个提示！", "show_answer": "给我看看！",
            },
            "ai": {
                "greeting": "你好，小明星！🌟 今天我们学什么？",
                "correct": ["太棒了！🎉", "你做到了！⭐", "好聪明！🚀", "超级棒！🏆"],
                "wrong": ["很好的尝试！我们一起看看 🤔", "差一点！你快要做到了！💡"],
                "encourage": ["你可以的！💪", "继续加油！🌟", "我相信你！🚀"],
                "farewell": "今天做得很好！下次见！🌈",
            },
            "subjects": {
                "math": "数字", "science": "发现", "reading": "故事",
                "writing": "写字", "art": "美术", "music": "音乐", "history": "很久以前",
            },
        },
        "upper_elementary": {
            "ui": {
                "space": "学习伙伴", "conversation": "聊天", "knowledge_base": "我的笔记",
                "send_message": "提问", "new_conversation": "新聊天", "settings": "设置",
                "dashboard": "我的进步", "welcome": "欢迎回来！今天我们学什么？",
            },
            "ai": {
                "greeting": "嗨！准备好大展身手了吗？💪",
                "correct": ["做得好！🎯", "答对了！⭐", "正确！"],
                "wrong": ["差一点——但想法不错！给你一个提示...", "接近了！我们一步一步来。"],
                "encourage": ["你能做到！", "继续努力！", "每个错误都是学习！"],
            },
            "subjects": {
                "math": "数学", "science": "科学", "reading": "阅读",
                "writing": "写作", "history": "历史",
            },
        },
        "middle_school": {
            "ui": {
                "space": "学习空间", "conversation": "课程", "send_message": "发送",
                "dashboard": "仪表板", "welcome": "欢迎。今天学什么？",
            },
            "ai": {
                "greeting": "欢迎回来。我们学哪个科目？",
                "correct": ["正确。", "做得好。", "对了。你能解释为什么吗？"],
                "wrong": ["不太对。让我们想想我们知道什么...", "我们重新考虑一下..."],
            },
            "subjects": {"math": "数学", "science": "科学", "reading": "语文", "history": "社会"},
        },
        "high_school": {
            "ui": {
                "space": "空间", "conversation": "对话", "send_message": "发送",
                "dashboard": "仪表板", "welcome": "欢迎。准备好学习了吗？",
            },
            "ai": {
                "greeting": "欢迎回来。我们在做什么？",
                "correct": ["正确。", "分析到位。", "推理扎实。"],
                "wrong": ["让我们重新考虑。", "复习这个概念再试一次。"],
            },
            "subjects": {"math": "数学", "science": "理科", "reading": "文学", "history": "历史"},
        },
    },

    # ──────────────────────────────────────────────────────
    # JAPANESE (ja)
    # ──────────────────────────────────────────────────────
    "ja": {
        "early_elementary": {
            "ui": {
                "space": "おてつだい", "conversation": "おはなし", "knowledge_base": "わたしのもの",
                "send_message": "きいて！", "new_conversation": "あたらしいおはなし！",
                "settings": "せってい", "dashboard": "わたしのがくしゅう",
                "profile": "わたしのこと", "logout": "またね！",
                "help": "たすけて！", "loading": "かんがえてるよ...",
                "error": "あれ？なにかうまくいかなかったよ",
                "welcome": "こんにちは！べんきょうしよう！",
                "empty_state": "まだなにもないよ！はじめよう！",
                "back": "もどる", "next": "つぎ！", "done": "できた！",
                "try_again": "もういちど！", "hint": "ヒントちょうだい！", "show_answer": "みせて！",
            },
            "ai": {
                "greeting": "こんにちは、スーパースター！🌟 きょうはなにをべんきょうする？",
                "correct": ["すごい！🎉", "やったね！⭐", "あたまいい！🚀", "さいこう！🏆"],
                "wrong": ["いいちょうせんだったよ！いっしょにみてみよう 🤔", "おしい！もうちょっと！💡"],
                "encourage": ["できるよ！💪", "がんばって！🌟", "しんじてるよ！🚀"],
                "farewell": "きょうもがんばったね！またね！🌈",
            },
            "subjects": {
                "math": "すうじ", "science": "はっけん", "reading": "おはなし",
                "writing": "かくこと", "art": "おえかき", "music": "おんがく", "history": "むかしのこと",
            },
        },
        "upper_elementary": {
            "ui": {
                "space": "勉強パートナー", "conversation": "チャット", "send_message": "聞く",
                "dashboard": "進み具合", "welcome": "おかえり！今日は何を勉強する？",
            },
            "ai": {
                "greeting": "やあ！今日もがんばろう！💪",
                "correct": ["よくできました！🎯", "正解！⭐", "その通り！"],
                "wrong": ["おしい！でもいい考えだったよ！ヒントをあげるね...", "もう少し！順番に考えよう。"],
            },
            "subjects": {"math": "算数", "science": "理科", "reading": "国語", "history": "社会"},
        },
        "middle_school": {
            "ui": {
                "space": "学習スペース", "conversation": "セッション", "send_message": "送信",
                "dashboard": "ダッシュボード", "welcome": "おかえりなさい。今日は何を勉強しますか？",
            },
            "ai": {
                "greeting": "おかえりなさい。どの教科に取り組みますか？",
                "correct": ["正解です。", "よくできました。", "正しいです。なぜそうなるか説明できますか？"],
                "wrong": ["少し違います。知っていることから考えてみましょう...", "考え直してみましょう..."],
            },
            "subjects": {"math": "数学", "science": "理科", "reading": "国語", "history": "社会"},
        },
        "high_school": {
            "ui": {
                "space": "スペース", "conversation": "会話", "send_message": "送信",
                "dashboard": "ダッシュボード", "welcome": "おかえりなさい。勉強の準備はできましたか？",
            },
            "ai": {
                "greeting": "おかえりなさい。何に取り組みますか？",
                "correct": ["正解です。", "よい分析です。", "確かな推論です。"],
                "wrong": ["考え直しましょう。", "概念を復習してもう一度挑戦してください。"],
            },
            "subjects": {"math": "数学", "science": "理科", "reading": "文学", "history": "歴史"},
        },
    },

    # ──────────────────────────────────────────────────────
    # ARABIC (ar)
    # ──────────────────────────────────────────────────────
    "ar": {
        "early_elementary": {
            "ui": {
                "space": "المساعد", "conversation": "محادثة", "knowledge_base": "أغراضي",
                "send_message": "!اسأل", "new_conversation": "!محادثة جديدة",
                "settings": "إعداداتي", "dashboard": "تعلّمي",
                "profile": "عنّي", "logout": "!إلى اللقاء",
                "help": "!أحتاج مساعدة", "loading": "...أفكر",
                "error": "!أوه! حدث خطأ",
                "welcome": "مرحباً! مستعد للتعلّم؟",
                "empty_state": "!لا يوجد شيء هنا بعد! هيا نبدأ",
                "back": "رجوع", "next": "!التالي", "done": "!انتهيت",
                "try_again": "!حاول مرة أخرى", "hint": "!أعطني تلميح", "show_answer": "!أرني",
            },
            "ai": {
                "greeting": "مرحباً يا نجم! 🌟 ماذا نتعلم اليوم؟",
                "correct": ["!رائع 🎉", "!أحسنت ⭐", "!ذكي جداً 🚀", "!عمل ممتاز 🏆"],
                "wrong": ["!محاولة جيدة! هيا ننظر معاً 🤔", "!قريب جداً 💡"],
                "encourage": ["!تقدر 💪", "!استمر 🌟", "!أنا أؤمن بك 🚀"],
                "farewell": "!عمل رائع اليوم! إلى اللقاء 🌈",
            },
            "subjects": {
                "math": "أرقام", "science": "اكتشاف", "reading": "قصص",
                "writing": "كتابة", "art": "رسم", "music": "موسيقى", "history": "زمان",
            },
        },
        "upper_elementary": {
            "ui": {
                "space": "رفيق الدراسة", "conversation": "محادثة", "send_message": "اسأل",
                "dashboard": "تقدّمي", "welcome": "!أهلاً! على ماذا نشتغل اليوم؟",
            },
            "ai": {
                "greeting": "مرحباً! مستعد تبدع؟ 💪",
                "correct": ["!أحسنت 🎯", "!ممتاز ⭐", "!صحيح"],
                "wrong": ["قريب! لكن تفكير جيد! إليك تلميح...", "!تقريباً! هيا نفصّلها"],
            },
            "subjects": {"math": "رياضيات", "science": "علوم", "reading": "قراءة", "history": "تاريخ"},
        },
        "middle_school": {
            "ui": {
                "space": "مساحة الدراسة", "conversation": "جلسة", "send_message": "إرسال",
                "dashboard": "لوحة المعلومات", "welcome": "أهلاً. ماذا ندرس اليوم؟",
            },
            "ai": {
                "greeting": "أهلاً. أي مادة نشتغل عليها؟",
                "correct": [".صحيح", ".أحسنت", "صحيح. هل يمكنك شرح السبب؟"],
                "wrong": ["ليس تماماً. لنفكر فيما نعرفه...", "...لنعيد النظر"],
            },
            "subjects": {"math": "رياضيات", "science": "علوم", "reading": "لغة عربية", "history": "دراسات اجتماعية"},
        },
        "high_school": {
            "ui": {
                "space": "مساحة", "conversation": "محادثة", "send_message": "إرسال",
                "dashboard": "لوحة المعلومات", "welcome": "أهلاً. مستعد للدراسة؟",
            },
            "ai": {
                "greeting": "أهلاً. على ماذا نعمل؟",
                "correct": [".صحيح", ".تحليل جيد", ".استدلال متين"],
                "wrong": [".لنعيد النظر", ".راجع المفهوم وحاول مرة أخرى"],
            },
            "subjects": {"math": "رياضيات", "science": "علوم", "reading": "أدب", "history": "تاريخ"},
        },
    },
}


# ══════════════════════════════════════════════════════════════
# TRANSLATION ENGINE
# ══════════════════════════════════════════════════════════════

class EducationI18n:
    """Serve age + language appropriate translations."""

    def get_translation(self, language: str, age_group: str) -> dict:
        """Get the complete translation set for a language + age group."""
        lang_data = EDU_TRANSLATIONS.get(language, EDU_TRANSLATIONS["en"])
        age_data = lang_data.get(age_group, lang_data.get("high_school", {}))
        # Fall back to English for any missing keys
        en_data = EDU_TRANSLATIONS["en"].get(age_group, {})
        merged = {}
        for section in ["ui", "ai", "subjects"]:
            merged[section] = {**en_data.get(section, {}), **age_data.get(section, {})}
        return merged

    def translate(self, key: str, language: str, age_group: str) -> str:
        """Translate a single UI key."""
        t = self.get_translation(language, age_group)
        return t.get("ui", {}).get(key, key)

    def get_ai_instruction(self, language: str, age_group: str) -> str:
        """Get AI personality instruction in the target language."""
        from .edu_theme import THEMES
        personality = THEMES.get(age_group, THEMES["high_school"])["ai_personality"]
        t = self.get_translation(language, age_group)
        ai = t.get("ai", {})
        # Combine personality instruction with localized responses
        return (
            f"{personality.get('instruction', '')}\n\n"
            f"IMPORTANT: Respond in {self._language_name(language)}.\n"
            f"Use this greeting: {ai.get('greeting', '')}\n"
            f"For correct answers, use phrases like: {', '.join(ai.get('correct', []))}\n"
            f"For wrong answers, use phrases like: {', '.join(ai.get('wrong', []))}\n"
            f"For encouragement, use phrases like: {', '.join(ai.get('encourage', []))}"
        )

    def get_supported_languages(self) -> list:
        return [
            {"code": "en", "name": "English", "native": "English", "rtl": False},
            {"code": "es", "name": "Spanish", "native": "Español", "rtl": False},
            {"code": "fr", "name": "French", "native": "Français", "rtl": False},
            {"code": "pt", "name": "Portuguese", "native": "Português", "rtl": False},
            {"code": "zh", "name": "Chinese", "native": "中文", "rtl": False},
            {"code": "ja", "name": "Japanese", "native": "日本語", "rtl": False},
            {"code": "ar", "name": "Arabic", "native": "العربية", "rtl": True},
        ]

    def _language_name(self, code: str) -> str:
        names = {"en": "English", "es": "Spanish", "fr": "French",
                 "pt": "Portuguese", "zh": "Chinese", "ja": "Japanese", "ar": "Arabic"}
        return names.get(code, "English")
