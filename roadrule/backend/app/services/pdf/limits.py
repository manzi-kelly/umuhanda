"""Native parser subprocess memory ceilings. Never apply inside the API/test process."""

import os

_job_handle = None


def limit_memory(megabytes: int):
    global _job_handle
    maximum = megabytes * 1024 * 1024
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64),
                ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD),
                ("min_working_set", ctypes.c_size_t),
                ("max_working_set", ctypes.c_size_t),
                ("active_processes", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class IO(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_uint64)
                for name in (
                    "read_ops",
                    "write_ops",
                    "other_ops",
                    "read_bytes",
                    "write_bytes",
                    "other_bytes",
                )
            ]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("basic", Basic),
                ("io", IO),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        _job_handle = kernel.CreateJobObjectW(None, None)
        information = Extended()
        information.basic.flags = 0x100
        information.process_memory = maximum
        if not _job_handle or not kernel.SetInformationJobObject(
            _job_handle, 9, ctypes.byref(information), ctypes.sizeof(information)
        ):
            raise RuntimeError("Native PDF memory limit could not be configured.")
        if not kernel.AssignProcessToJobObject(_job_handle, kernel.GetCurrentProcess()):
            raise RuntimeError("Native PDF memory limit could not be attached.")
    else:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (maximum, maximum))
