# Vendored libraries

Inlined into graph/index.html by tools/knowledge_graph.py, so the page opens offline
from file:// and makes no network calls. Each file was taken from its npm tarball,
verified against the registry's published sha512 integrity on 2026-10-21.
three.min.js is loaded first: 3d-force-graph uses window.THREE when it exists, so
the page and the renderer share one copy of three.js.

## three 0.160.0

- File: `three.min.js` (from `package/build/three.min.js`, 669884 bytes)
- Tarball: https://registry.npmjs.org/three/-/three-0.160.0.tgz
- Tarball integrity: sha512-DLU8lc0zNIPkM7rH5/e1Ks1Z8tWCGRq6g8mPowdDJpw1CFBJMU7UoJjC6PefXW7z//SSl0b2+GCw14LB+uDhng==
- File sha256: 170c6789f43217c96b3170f4b42fafe135de7f7cd48497a4218f9757ee1d49fa
- Licence: MIT

```
The MIT License

Copyright © 2010-2023 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

## 3d-force-graph 1.73.3

- File: `3d-force-graph.min.js` (from `package/dist/3d-force-graph.min.js`, 691294 bytes)
- Tarball: https://registry.npmjs.org/3d-force-graph/-/3d-force-graph-1.73.3.tgz
- Tarball integrity: sha512-azb65Lwn2yr/fJ4+qrxjmstVxogjzwJIZL/fdboCKBg6ph/FLW+xdvYFEBZW92XxBn1C8yRKS3d2VkVT3BzLSw==
- File sha256: 19b3be27040fc894e56d684d53c5f62526c25e5d27f37e8fe91fafff605e4ef4
- Licence: MIT

```
MIT License

Copyright (c) 2017 Vasco Asturiano

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
