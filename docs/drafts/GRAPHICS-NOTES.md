# Bug Report on Graphics

The pictures can be found here: 

/home/constantin/nexus/projects/cod-nexus-dev/pictures/folders.png
/home/constantin/nexus/projects/cod-nexus-dev/pictures/GUI-project-2.png
/home/constantin/nexus/projects/cod-nexus-dev/pictures/GUI-project-3.png
/home/constantin/nexus/projects/cod-nexus-dev/pictures/GUI-project-4.png
/home/constantin/nexus/projects/cod-nexus-dev/pictures/GUI-project-5.png
/home/constantin/nexus/projects/cod-nexus-dev/pictures/GUI-project-6.png
/home/constantin/nexus/projects/cod-nexus-dev/pictures/GUI-project-7.png
/home/constantin/nexus/projects/cod-nexus-dev/pictures/GUI-project.png
/home/constantin/nexus/projects/cod-nexus-dev/pictures/GUI-start.png
/home/constantin/nexus/projects/cod-nexus-dev/pictures/TUI-project-modules.png
/home/constantin/nexus/projects/cod-nexus-dev/pictures/TUI-start.png


##GUI

GUI-project.png: 
    - Shows that the project still have module types displayed in the project-tile

GUI-project-2.png, GUI-project-3.png, GUI-project-4.png, GUI-project-5.png, GUI-project-6.png, 
GUI-project-7.png : 
    - Module buttons are hidden behind the the actual screen.
    - Input Window is open by default. Should not be open by default.
    - Clicking the button for Input opens a secondary input window overlapping with the first one. 
    - Fix this to have the input window not be visible on default but activate on clicking the keyboard 
    - Shell and Claude both open scolled down, also are scrollable horizontally. Fix horizontal width and make Claude and Shell display all text within the margins, and starting the conversation on the top for each. 

##TUI

TUI-project-start.png:
    - just a reference for "this looks good". Because i want the next thing to look like it. 

TUI-project-modules.png:
    - The modules should be displayed in the same manner as the projects in the starting screen. The current state is just janky. 


## Global

folders.png: 
    - globally, between projects and modules, the module-prefix is still applied to the project folders. This is not necessary anymore. 

