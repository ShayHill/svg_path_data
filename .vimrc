vim9script

# run the main python file
nnoremap <leader>m :update<CR>:ScratchTermReplaceU venv/Scripts/python.exe src/svg_path_data/main.py<CR>

# resize the code window after running a python file
nnoremap <leader>w :resize 65<CR>
