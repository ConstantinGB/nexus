"""
LocalAI module — AI-assisted setup and runtime UI for local AI models.

Supports LLMs (text generation), diffusion models (image generation),
and other locally hosted AI workloads. Claude detects hardware, searches
the web for installation info, and generates a one-time bash setup script.

Structure:
  hw_detect.py     — blocking hardware detection (GPU, RAM, CPU, OS, disk)
  setup_screen.py  — LocalAISetupScreen: config → AI work → review → install → done
  project_screen.py — LocalAIProjectScreen: prompt input + inference output UI
"""
