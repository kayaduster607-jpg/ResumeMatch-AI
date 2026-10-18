"""Convenience launcher.

Interactive:
  python run_job_crawler.py

Login:
  python run_job_crawler.py login --platforms all

Run directly:
  python run_job_crawler.py run --resume backend/data/samples/sample_resume.txt --keyword AI实习生 --city 广州
"""

from job_crawler.__main__ import main

if __name__ == "__main__":
    main()
