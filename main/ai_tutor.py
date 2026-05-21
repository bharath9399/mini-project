import re
import random

class AITutor:
    def __init__(self):
        self.motivational_prefixes = [
            "Great question! \ud83d\udc4d ",
            "I'm glad you asked that. ",
            "That's a very common doubt! Let's clear it up. ",
            "Excellent point. Here is how we can break it down: ",
            "I totally understand why that's confusing. Let's look at it step-by-step. "
        ]
        
    def generate_response(self, message: str, subject: str = "general") -> str:
        msg = message.lower()
        
        # 1. Greetings
        if msg in ["hi", "hello", "hey", "hii"]:
            return "Hi there! \ud83d\udc4b I'm your AI Study Partner. What topic or doubt can I help you with today?"
            
        # 2. Physics - Newton's Laws
        if "newton" in msg and ("second" in msg or "2nd" in msg or "law" in msg):
            return (random.choice(self.motivational_prefixes) + 
                    "Newton\u2019s Second Law states that Force = Mass \u00d7 Acceleration (F = ma). "
                    "It means heavier objects need more force to move. \n\n"
                    "*Example*: Pushing a heavy truck requires much more force than pushing a small bicycle to reach the same speed. \n"
                    "Does this make sense?")
                    
        # 3. Math - Integration
        if "integration" in msg or "calculus" in msg:
            return (random.choice(self.motivational_prefixes) +
                    "Let\u2019s understand integration step by step. Integration is basically the reverse of differentiation. "
                    "It is used to find the **area under curves**, volumes, or central points. \n\n"
                    "Step 1: Identify the function f(x).\n"
                    "Step 2: Apply the integration rules (like the power rule: \u222bx^n dx = x^(n+1)/(n+1)).\n"
                    "Which specific part of integration is confusing you? The formulas or the concept?")
                    
        # 4. Chemistry - Bonds
        if "bond" in msg or ("covalent" in msg and "ionic" in msg):
            return (random.choice(self.motivational_prefixes) +
                    "In Chemistry, an **Ionic bond** is formed when one atom completely transfers electrons to another (like NaCl). "
                    "A **Covalent bond** is when atoms share electrons (like H2O). \n\n"
                    "Are you working on a specific molecule right now?")
                    
        # 5. Generic Doubt Handling
        if "doubt" in msg or "stuck" in msg or "help" in msg:
            return "I understood your doubt \ud83d\udc4d. Which part is confusing \u2014 the formula, the core concept, or the problem-solving steps?"
            
        # 6. Fallback Subject-Specific Logic
        prefix = random.choice(self.motivational_prefixes)
        if "math" in subject.lower():
            return prefix + "In Mathematics, always start by writing down the given values and the formula you need. What are the variables given in your problem?"
        elif "phys" in subject.lower():
            return prefix + "For Physics problems, drawing a quick diagram (like a Free Body Diagram) helps immensely. Have you tried drawing it out?"
        elif "chem" in subject.lower():
            return prefix + "In Chemistry, make sure your chemical equations are balanced before doing any mole calculations. Let's check the balanced equation first."
        elif "bio" in subject.lower():
            return prefix + "In Biology, visualizing the system (like the cell structure or human anatomy) makes it much easier to remember. Want me to explain the structure?"
            
        return prefix + "To solve this, let's break it down into smaller steps. What is the very first thing you think we should do?"

# Instantiate a singleton
ai_tutor = AITutor()
