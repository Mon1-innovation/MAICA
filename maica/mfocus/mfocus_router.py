"""
We're writing this basically to replace the old structure of MFocus. They're too messy.
Now that we're implementing RAG approach of memory, we're splitting MFocus into multiple parts.
Like:

- Main router
    - LLM
        - Agent tools
    - RAG
    - Data management
        - DB sync
        - Auto-memory stuff

It's rough but, we'll find a better approach as we go.
"""



class MfMainRouter():
    """
    Main router, we want it to directly hand in the informations, and we add them into prompt.
    As called, it handles all MFocus routing.
    """
    def __init__(self):
        pass