import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="example-pkg-your-username",
    version="0.0.1",
    author="Frappe Technologies Pvt. Ltd.",
    author_email="author@example.com",
    description="A full text search implementation in Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/safwansamsudeen/apex-search",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
