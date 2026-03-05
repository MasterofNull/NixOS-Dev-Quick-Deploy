"""
Vim Editor Agent Yank Functionality Implementation

This module implements the yank functionality for a Vim editor agent,
based on the conversation history about implementing yank mode in a Vim editor.
"""

class VimEditorAgent:
    def __init__(self):
        self.buffer = []  # Represents the text buffer
        self.cursor_position = 0  # Current cursor position
        self.mode = "NORMAL"  # Current mode: NORMAL, INSERT, VISUAL
        self.clipboard = ""  # Stores yanked text
        self.visual_start = None  # Starting position for visual selection
        
    def enter_visual_mode(self):
        """Enter visual mode and set the starting position"""
        self.mode = "VISUAL"
        self.visual_start = self.cursor_position
        return "Entered VISUAL mode"
    
    def exit_visual_mode(self):
        """Exit visual mode"""
        self.mode = "NORMAL"
        self.visual_start = None
        return "Exited VISUAL mode"
    
    def move_cursor(self, direction, count=1):
        """Move cursor in the specified direction"""
        if direction == "up":
            self.cursor_position = max(0, self.cursor_position - count)
        elif direction == "down":
            self.cursor_position = min(len(self.buffer), self.cursor_position + count)
        elif direction == "left":
            # Assuming we're working with a single line for simplicity
            self.cursor_position = max(0, self.cursor_position - count)
        elif direction == "right":
            self.cursor_position = min(len(self.buffer) if self.buffer else 0, self.cursor_position + count)
            
    def yank_text(self, motion=None, count=1):
        """
        Yank (copy) text based on motion or in visual mode
        
        Args:
            motion (str): The motion to determine what to yank (e.g., 'w', 'e', 'j', 'k', '$')
            count (int): Number of times to repeat the motion
        
        Returns:
            str: Status message
        """
        if self.mode == "VISUAL":
            # Yank selected text in visual mode
            start_pos = min(self.visual_start, self.cursor_position)
            end_pos = max(self.visual_start, self.cursor_position)
            
            if self.buffer:
                # Extract the text between start and end positions
                text = ''.join(self.buffer) if isinstance(self.buffer, list) else self.buffer
                self.clipboard = text[start_pos:end_pos]
                self.exit_visual_mode()
                return f"Yanked {len(self.clipboard)} characters"
            else:
                return "Nothing to yank"
                
        elif self.mode == "NORMAL":
            # Yank based on motion commands
            start_pos = self.cursor_position
            
            if motion == "w":  # Yank word
                # Find end of current word
                pos = start_pos
                text = ''.join(self.buffer) if self.buffer else ""
                
                # Skip any leading whitespace
                while pos < len(text) and text[pos].isspace():
                    pos += 1
                
                # Move to end of word
                while pos < len(text) and not text[pos].isspace():
                    pos += 1
                    
                self.clipboard = text[start_pos:pos]
                self.cursor_position = pos
                return f"Yanked '{self.clipboard}'"
                
            elif motion == "$":  # Yank to end of line
                text = ''.join(self.buffer) if self.buffer else ""
                self.clipboard = text[start_pos:]
                return f"Yanked '{self.clipboard}'"
                
            elif motion == "0":  # Yank from beginning of line
                text = ''.join(self.buffer) if self.buffer else ""
                self.clipboard = text[:start_pos]
                return f"Yanked '{self.clipboard}'"
                
            elif motion == "gg":  # Yank from beginning of file
                text = ''.join(self.buffer) if self.buffer else ""
                self.clipboard = text[:start_pos]
                self.cursor_position = 0
                return f"Yanked {len(self.clipboard)} characters from beginning"
                
            elif motion == "G":  # Yank to end of file
                text = ''.join(self.buffer) if self.buffer else ""
                self.clipboard = text[start_pos:]
                self.cursor_position = len(text)
                return f"Yanked {len(self.clipboard)} characters to end"
                
            elif motion == "j":  # Yank current line and next 'count' lines
                # For simplicity, assuming each element in buffer is a line
                start_line_idx = self._get_line_index(start_pos)
                end_line_idx = min(len(self.buffer), start_line_idx + count)
                
                if self.buffer:
                    yanked_lines = self.buffer[start_line_idx:end_line_idx + 1]
                    self.clipboard = ''.join(yanked_lines)
                    # Move cursor to beginning of the line after the yanked lines
                    if end_line_idx < len(self.buffer):
                        self.cursor_position = sum(len(line) for line in self.buffer[:end_line_idx])
                    else:
                        self.cursor_position = len(''.join(self.buffer))
                    return f"Yanked {len(yanked_lines)} lines"
                else:
                    return "Nothing to yank"
                    
            elif motion == "k":  # Yank current line and previous 'count' lines
                start_line_idx = self._get_line_index(start_pos)
                end_line_idx = max(0, start_line_idx - count)
                
                if self.buffer:
                    yanked_lines = self.buffer[end_line_idx:start_line_idx + 1]
                    self.clipboard = ''.join(yanked_lines)
                    # Move cursor to beginning of the line after the yanked lines
                    self.cursor_position = sum(len(line) for line in self.buffer[:end_line_idx])
                    return f"Yanked {len(yanked_lines)} lines"
                else:
                    return "Nothing to yank"
                    
            elif motion is None:  # Default: yank current line
                line_idx = self._get_line_index(start_pos)
                if 0 <= line_idx < len(self.buffer):
                    self.clipboard = self.buffer[line_idx]
                    return f"Yanked line: '{self.clipboard}'"
                else:
                    return "Nothing to yank"
                    
        else:
            return "Cannot yank in current mode"
    
    def _get_line_index(self, position):
        """Helper to get line index from character position"""
        if not self.buffer:
            return 0
            
        current_pos = 0
        for i, line in enumerate(self.buffer):
            if current_pos <= position < current_pos + len(line):
                return i
            current_pos += len(line)
        return len(self.buffer) - 1
    
    def paste_after(self):
        """Paste clipboard content after cursor position"""
        if self.buffer and self.clipboard:
            text = ''.join(self.buffer)
            before = text[:self.cursor_position]
            after = text[self.cursor_position:]
            new_text = before + self.clipboard + after
            self.buffer = [new_text]  # Simplified: treating as single line
            self.cursor_position += len(self.clipboard)
            return f"Pasted '{self.clipboard}'"
        else:
            return "Nothing to paste"
    
    def paste_before(self):
        """Paste clipboard content before cursor position"""
        if self.buffer and self.clipboard:
            text = ''.join(self.buffer)
            before = text[:self.cursor_position]
            after = text[self.cursor_position:]
            new_text = before + self.clipboard + after
            self.buffer = [new_text]  # Simplified: treating as single line
            return f"Pasted '{self.clipboard}'"
        else:
            return "Nothing to paste"


# Example usage:
if __name__ == "__main__":
    # Initialize the Vim editor agent
    vim_agent = VimEditorAgent()
    
    # Load some sample text into the buffer
    vim_agent.buffer = ["Hello world!", "This is line 2.", "Final line here."]
    vim_agent.cursor_position = 0
    
    print(f"Initial mode: {vim_agent.mode}")
    print(f"Buffer: {vim_agent.buffer}")
    
    # Example 1: Yank current line (yy)
    result = vim_agent.yank_text()
    print(f"\nYank current line: {result}")
    print(f"Clipboard: '{vim_agent.clipboard}'")
    
    # Example 2: Enter visual mode, move cursor, then yank
    vim_agent.cursor_position = 6  # Position at 'w' in "world!"
    result = vim_agent.enter_visual_mode()
    print(f"\n{result}")
    vim_agent.move_cursor("right", 5)  # Move to end of "world!"
    result = vim_agent.yank_text()
    print(f"Visual yank: {result}")
    print(f"Clipboard: '{vim_agent.clipboard}'")
    
    # Example 3: Yank to end of line (y$)
    vim_agent.cursor_position = 0  # Back to start of line
    vim_agent.mode = "NORMAL"
    result = vim_agent.yank_text("$")
    print(f"\nYank to end of line: {result}")
    print(f"Clipboard: '{vim_agent.clipboard}'")
    
    # Example 4: Paste the yanked text
    result = vim_agent.paste_after()
    print(f"\nPaste after cursor: {result}")
    print(f"Updated buffer: {vim_agent.buffer}")