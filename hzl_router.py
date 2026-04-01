"""
hzl_router.py -- Re-exports from hzl-cluster package.
Install: pip install git+https://github.com/ryannlynnmurphy/hzl-cluster.git
"""

from hzl_cluster.router import *  # noqa: F401,F403
from hzl_cluster.router import HZLRouter, RoutingDecision, CircuitBreaker, classify_task
