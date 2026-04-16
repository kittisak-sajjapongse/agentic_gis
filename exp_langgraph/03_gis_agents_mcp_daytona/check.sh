#!/usr/bin/env bash
FILES="\
    MgmtDept.py\
    MgmtAgent.py\
    IRAgent.py\
    OGAgent.py\
    AgentBase.py\
    IAgentState.py\
    main.py\
"
python3 -m mypy $FILES
black $FILES