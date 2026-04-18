window.QUESTIONNAIRE_CONFIG = {
  "intake": {
    "version": 1,
    "steps": [
      {
        "key": "name",
        "type": "text",
        "label": "Step 1",
        "title": "What is your name?",
        "hint": "We use this in our emails and to organize your photos.",
        "required": true,
        "placeholder": "First and last name"
      },
      {
        "key": "yardGoal",
        "type": "textarea",
        "label": "Step 2",
        "title": "What are you hoping to improve?",
        "hint": "A sentence or two is perfect.",
        "required": false,
        "placeholder": "Front beds, entry feel, curb appeal..."
      },
      {
        "key": "yardNotes",
        "type": "textarea",
        "label": "Step 3",
        "title": "Tell us a little about your yard or goals.",
        "hint": "Share anything helpful about style, maintenance, or what feels off.",
        "required": false,
        "placeholder": "Anything you want us to keep in mind..."
      },
      {
        "key": "photos",
        "type": "upload",
        "label": "Step 4",
        "title": "Upload a photo of your yard (optional).",
        "hint": "Quick phone photos are great. You can skip this and still submit.",
        "required": false
      },
      {
        "key": "address",
        "type": "text",
        "label": "Step 5",
        "title": "What is your address? (optional but helpful)",
        "hint": "If easier, just include city and street.",
        "required": false,
        "placeholder": "Optional address"
      },
      {
        "key": "email",
        "type": "email",
        "label": "Step 6",
        "title": "What is your email?",
        "hint": "We'll send a thoughtful follow-up. No spam.",
        "required": true,
        "placeholder": "you@example.com"
      }
    ]
  }
};
