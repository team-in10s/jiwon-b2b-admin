from setuptools import setup, find_packages

setup(
    name="jiwon-b2b-admin",
    packages=find_packages(),
    package_data={'': ['*']},
    include_package_data=True,
    install_requires=[
        "streamlit",
        "playwright",
        "openai",
        "langchain",
        "psycopg2-binary",
        "python-dotenv",
        "supabase",
        "pandas",
        "numpy",
        "aiohttp",
        "asyncio",
        "python-dateutil",
        "pytz",
        "requests",
        "urllib3",
        "beautifulsoup4"
    ],
) 