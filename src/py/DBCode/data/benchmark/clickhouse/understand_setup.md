## python understand 连接

### 下载Understand-3.1.670-Linux-64bit.tgz
https://github.com/catfish416/mynotes/blob/3c2422230ec9c02bda21d8560d55186e14285ffe/software/Understand-3.1.670-Linux-64bit.tgz#L2

证书：09E58CD1FB79

### 环境变量
```=bash
sudo vim ~/.bashrc 
```

添加（不确定哪些是必要的，可能都没用）
```=bash
source /opt/clash/script/common.sh && source /opt/clash/script/clashctl.sh && watch_proxy
export PATH=/home/gg/understand/scitools/bin/linux64:$PATH
export STIHOME=/home/gg/understand/scitools:$STIHOME
export PATH=/home/gg/understand/scitools/bin/linux64/python:$PATH
export PYTHONPATH=/home/gg/understand/scitools/bin/linux/python:$PYTHONPATH
export LD_LIBRARY_PATH=/home/gg/understand/scitools/bin/linux64:$LD_LIBRARY_PATH
```

### python代码
```=python
import sys
import os
sys.path.append('/home/gg/understand/scitools/bin/linux64/python')
import understand
```


