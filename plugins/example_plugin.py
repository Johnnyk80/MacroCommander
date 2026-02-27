"""
Hello Plugin Example

Demonstrates:
- Parameter input
- Activity Log output
- Returning status to macro engine
"""

def register(registry):
    """
    Called automatically by plugin_loader.
    """

    def hello_action(params):
        """
        Action execution function.
        """

        name = params.get("name", "World")

        logger = params.get("_logger")
        controller_id = params.get("_controller_id")

        message = f"Hello {name}! (Controller {controller_id})"

        # Log to Activity Log if available
        if logger:
            try:
                logger.log(f"[HelloPlugin] {message}")
            except Exception:
                pass

        # You could do real work here instead of logging
        # Example:
        # change sound device
        # launch program
        # call API
        # etc.

        return True, message

    # Register action with system
    registry.register_action(
        action_id="hello.world",
        name="Hello World (Plugin)",
        description="Test plugin that writes to Activity Log.",
        schema={
            "name": {
                "type": "string",
                "label": "Name",
                "required": False,
                "default": "World"
            }
        },
        run=hello_action
    )
