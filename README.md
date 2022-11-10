# Remote.py

A python port of the [remote](https://github.com/wellcometrust/remote) tool for controlling remote instances on AWS.

# Getting started

The package is pip installable and can be installed directly from github with:

```
pip install git+https://github.com/ivyleavedtoadflax/remote.py.git
```

# Usage

Add the name of your default instance to the config file

```
remotepy config add
```

Check that is was set

```
remotepy config show
```

Start the instance:

```
remotepy start
```

Connect to the instance with ssh

```
remotepy connect
```

Connect to the instance with ssh and port forwarding and verbosity

```
remotepy connect -p 1234:localhost:1234 -v
```

Stop the instance:

```
remotepy stop
```

Get the instance status:

```
remotepy status
```

To run commands on a different instance, pass the name as an argument:

```
remotepy status another_ec2_instance
```


# For development

Create a virtual environment and install the package

```
virtualenv - -python 3.8 venv
source venv/bin/activate
pip install ".[dev]"
```

# Run tests


```
pytest
```

# PyPi

```
python -m build
twine upload dist/
```

Note that you need to setup up authentication to PyPi for this work work.
