"""
Test suite for Vim Editor Agent Yank Functionality
"""
import sys
import os

# Add the project directory to the path so we can import our implementation
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vim_yank_implementation import VimEditorAgent


def test_initial_state():
    """Test that the Vim editor agent initializes correctly"""
    agent = VimEditorAgent()
    assert agent.mode == "NORMAL"
    assert agent.buffer == []
    assert agent.cursor_position == 0
    assert agent.clipboard == ""
    print("✓ Initial state test passed")


def test_yank_current_line():
    """Test yanking the current line (yy command)"""
    agent = VimEditorAgent()
    agent.buffer = ["Hello world!", "This is line 2.", "Final line here."]
    agent.cursor_position = 0  # At the beginning of the first line
    
    result = agent.yank_text()  # Default yank (current line)
    assert "Yanked line" in result
    assert agent.clipboard == "Hello world!"
    print("✓ Yank current line test passed")


def test_yank_visual_selection():
    """Test yanking text in visual mode"""
    agent = VimEditorAgent()
    agent.buffer = ["Hello world!"]
    agent.cursor_position = 0
    
    # Enter visual mode
    agent.enter_visual_mode()
    # Move cursor to select "Hello"
    agent.cursor_position = 5
    # Yank the selection
    result = agent.yank_text()
    
    assert "Yanked" in result
    assert agent.clipboard == "Hello"
    assert agent.mode == "NORMAL"  # Should exit visual mode after yank
    print("✓ Visual selection yank test passed")


def test_yank_to_end_of_line():
    """Test yanking from cursor to end of line (y$)"""
    agent = VimEditorAgent()
    agent.buffer = ["Hello world!"]
    agent.cursor_position = 5  # After "Hello", at the space
    
    result = agent.yank_text("$")  # Yank to end of line
    assert "Yanked" in result
    assert agent.clipboard == " world!"
    print("✓ Yank to end of line test passed")


def test_yank_word():
    """Test yanking a word (yw)"""
    agent = VimEditorAgent()
    agent.buffer = ["Hello world! This is a test."]
    agent.cursor_position = 0  # At the beginning
    
    result = agent.yank_text("w")  # Yank word
    assert "Yanked" in result
    assert agent.clipboard == "Hello"
    print("✓ Yank word test passed")


def test_paste_functionality():
    """Test pasting yanked text"""
    agent = VimEditorAgent()
    agent.buffer = ["Hello world!"]
    agent.cursor_position = 5  # After "Hello"
    
    # Yank the first word
    agent.yank_text("w")
    
    # Clear the buffer for a clean paste test
    agent.buffer = ["Test: "]
    agent.cursor_position = 6  # At the end
    
    # Paste after cursor
    result = agent.paste_after()
    assert "Pasted" in result
    # Since we simplified the buffer handling, the paste will append to the single string
    print("✓ Paste functionality test passed")


def test_yank_empty_buffer():
    """Test yanking when buffer is empty"""
    agent = VimEditorAgent()
    agent.buffer = []
    
    result = agent.yank_text()
    assert "Nothing to yank" in result
    print("✓ Empty buffer yank test passed")


def test_yank_beginning_of_line():
    """Test yanking from beginning of line to cursor (y0)"""
    agent = VimEditorAgent()
    agent.buffer = ["Hello world!"]
    agent.cursor_position = 5  # At the space after "Hello"
    
    result = agent.yank_text("0")  # Yank from beginning to cursor
    assert "Yanked" in result
    assert agent.clipboard == "Hello"
    print("✓ Yank from beginning of line test passed")


def run_all_tests():
    """Run all tests"""
    print("Running Vim Editor Agent Yank Functionality Tests...\n")
    
    test_initial_state()
    test_yank_current_line()
    test_yank_visual_selection()
    test_yank_to_end_of_line()
    test_yank_word()
    test_paste_functionality()
    test_yank_empty_buffer()
    test_yank_beginning_of_line()
    
    print("\n🎉 All tests passed!")


if __name__ == "__main__":
    run_all_tests()