import os
from setuptools import setup, find_packages

setup(
    name="tradelocker-python",
    version="0.1.0",
    description="Prop-Firm safe Python connector for TradeLocker with biological session fingerprinting.",
    long_description=open("README.md").read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="Antigravity (on behalf of Nicholas Macaskill)",
    url="https://github.com/nicholasmacaskill/tradelocker-python",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
