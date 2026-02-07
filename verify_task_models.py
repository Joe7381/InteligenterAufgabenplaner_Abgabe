print("Importing task_models")
try:
    import task_models
    print("TaskDB attributes:", dir(task_models))
    from task_models import TaskDB
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
