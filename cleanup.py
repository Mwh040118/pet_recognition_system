import os
for f in ['D:/pet_recognition_system/gen_resume.py',
          'D:/pet_recognition_system/check_resume.py',
          'D:/pet_recognition_system/list_files.py']:
    if os.path.exists(f):
        os.remove(f)
        print("removed", f)
