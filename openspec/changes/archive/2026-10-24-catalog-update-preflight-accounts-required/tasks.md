# Tasks

## 1. Mirror the builder in the sizer (app/EngineController.cpp)

- [x] 1.1 `sumRequestedBytes`: installed + update requests sum required
      files plus the optional bundle exactly when audio is requested
- [x] 1.2 Change validates; existing C++ catalog tests unaffected (parser
      fixtures untouched)

## 2. Verification

- [x] 2.1 Diff review: the sizer's update rule matches the transfer's
      update rule file-for-file (required always; optional iff audio)
- [x] 2.2 The silent-tap path (`nothing` on a genuine update) is unreachable
      afterwards: an update always needs at least its required bytes
