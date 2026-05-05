# Conceptualizing a major shift in design philosophy for this project.

## Rectifying a mistake i made in the beginning

### This is more of a free associative rant that helps me get my idea across

I made the terrible mistake of making each module a project, or vice versa. 

Instead, the "custom module" should have given me the right idea from the start.

Every project is custom. And every project should have access to every module when needed.

It should be "New Project", then a list of all existing functions, including the new "custom" for designing your custom function that you need.

When opening the project, you have access to different applications (the modules) that can use and store data from and in the project files. Or in short: Use module, read/write/execute here. 

You choose applications for a project via tickbox, you can edit your choice later. The number of tools is determined by the user based on the scope of "the project".

Git, Backup, LocalAI, Security, Home should be more in the category of "System Modules", because from the users perspective ... how many different git accounts should they require? We made a "nice to have" into a complete feature. Same for Backup - backup can just get multiple schedules to back up different things. I know that, i have worked with bacula, so why did i make it so complicated? You also generally only need one LocalAI setup, and sice the user is planning to use a local AI setup to also power their nexus, they probably don't need a second separate one. 

Those features SHOULD still be available as "dedicated" features to a project, IF that project requires it, but that should be optional. It can be a second category of modules presented when starting a new Project. 

And the other modules, the Codex, Journal, Research, YouTube, and all other features, usually a project requires multiple. And we don't need Codex AND Journal AND Notes AND Tasks in the way we have it now.
- Tasks will be a module
- Calendar will be a module
- Notes will be a module

I think we can refactor it that way by changing reeeelatively little. 

The TUI should be fairly easy, since it is largely totally different screens. I would keep the starting screen that shows all projects, but they will basically just open the folder that IS the project, and on opening it shows all available modules + a config button (for the project) that let's the user make changes (Check-Unchek modules and system modules and other adjustments), and when clicking on the module, it now opens the module screen as we already have it in the TUI. We can still use all functions as they were, but now they automatically map to the project directory. 

The "Chat" window or wiget is still not as i would like it. And the three buttons take up a lot of space. I would prefer one button, that when pressed opens a little dropdown menu that lets you choose the input method you want. AI Chat, Claude, Shell. Just a keyboard symbol should suffice. 


For the GUI it looks a bit different. 
We keep the project tiles on the starting screen (this time for the new definition of project), and we keep the "open projects" tabs with the "Home" one. But we will rework the "Operator" and everything else regarding that. The Operator is dead, both in GUI and TUI, because - as i said earlier - the notes, calendar and tasks become modules themselves, as they should be. 
Instead, the GUI will do what the TUI can't. Just have a button / icon for each module (which, as we established, will be checkbox opt-ins) that's part of the project. 
And the "Chat" will Just be another one of those. It will have a Keyboard symbol (not called chat) and open the input window, that can be configured (little settings button) to show either Local AI Chat, Claude or the Shell. (And again, only the AI chat with its own nexus interface, claude and shell should be loaded as are, not just their output rendered. Even in the gui, you should easily just type a bit of stuff in the shell, and i want the user to have the claude code experience with claude.)


Functionally modules will still be modules and i think they will now work as intended. It also gives us the opportunity to , while we are at it, clean up some things.

I'm fine with losing the projects as they are, most of them were just proof of concept test sandboxes anyway and i have already saved all the files elsewhere. 