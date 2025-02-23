See the apworld this randomizer program expects to receive an .json from in order to shuffle game files: https://github.com/ManNamedGarbo/RE5_AP

How to use
1. Extract the latest release zip to a folder.
2. Generate a game via the apworld (refer to Archipelago FAQs and my RE5_AP github linked above for how to do this)
3. After generation, the output zip will have a json file named after your slot. Take this and place it inside of the folder with the randomizer program.
![Screenshot_1](https://github.com/user-attachments/assets/6c7e6aeb-ddeb-4682-8fc9-7c94e444ba56)
4. Run the AP Arc Rando.exe file (if you are running from source here on github, open a cmd/powershell to the folder and type `py ap_arc.py` to run the script)
5. A box will appear asking you to select a folder. Navigate to where your Resident Evil 5 is installed and select the "Archive" folder found by default at `.\Resident Evil 5\nativePC_MT\Image\Archive`
6. Let the program do it's thing. If it succeeds it will generate a folder named after your json file you got from archipelago. It will also create a log.txt (for ARCtool.exe) and a logs folder (for AP Arc Rando). If you run into any randomization errors please make sure to include these logs when asking for help in the discord!
7. NOTE: BACK UP YOUR GAME FILES BEFORE DOING SO! MY PROGRAM DOES NOT HAVE A WAY TO BACK UP NEARLY 5 GIGS WORTH OF FILES, SO IT'S UP TO YOU TO DO SO BEFORE TAKING THIS STEP. Take the files from the newly created folder and place them into your Resident Evil 5 archive folder.
8. If you are playing with a coop partner, they will need to do this as well before you connect to each other. If you pick up an item that is different for another player (i.e. one player picks up an M92F, other player sees it as a S75), the session will desync and possibly crash to the main menu.
9. Connect to archipelago using the client included with the apworld! (Work in progress, currently not available.)
