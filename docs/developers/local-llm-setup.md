# How to set up and test LLMs locally with Ollama and VS Code
1. Download and install Ollama: "https://ollama.com/download"
2. Open the Ollama app (just leave it on the "Apps" tab, it runs in the background)
3. Find an Ollama model you want to use: "https://ollama.com/search"
4. Choose a model and then run the command `ollama run <your-model:size>` (i.e. `ollama run gemma4:e2b`) in any terminal
5. Ollama will download and start the model. When it's ready it will say this: `Send a message (/? for help)`
6. Open VS Code and add earthdata-mcp to your VS Code MCP servers
7. In VS Code, make sure the "Secondary Side Bar" is visible (View > Appearance > Secondary Side Bar) --> This is the VS Code "Agent Mode" bar
8. VS Code Agent Mode runs on Copilot using the model `MAI-Code-1.1-Flash`, but you can add your own models --> Below the prompt field, click on the model dropdown that says "Auto"
9. Click "Manage Models..." and then "+ Add Models..." button in the "Language Models" window that opens
10. Choose Ollama, and then close and reopen the "Language Models" window (you may have to restart VS Code and wait a bit)
11. VS Code should auto-detect the Ollama model you ran earlier, so click the eyeball button in the first column next to your model so that it becomes an open eye with no slash. This means it's visible in the model dropdown
12. Run the python startup command for earthdata-mcp: `uv run server.py http` (Make sure everything starts OK)
13. Under "MCP SERVERS - INSTALLED" in the "Extensions" side bar, click on earthdata-mcp's gear icon and click "Start Server"
14. You now have earthdata-mcp running, connected to VS Code through VS Code's MCP server config. VS Code knows about Ollama models, such as the one you're running, because you added it to Agent Mode's model table. Prompts can now be entered in the prompt field using your currently running model once you select it from the model dropdown (the button that says "Auto"), and that model can use earthdata-mcp
