"""
Gestión del ciclo de vida de ficheros temporales de la sesión.
"""

import os
import atexit
import shutil
import tempfile
import hashlib
import streamlit as st


def init_session_dir() -> str:
    """Crea (o recupera) el directorio temporal de la sesión."""
    if "temp_dir" not in st.session_state:
        temp_dir = tempfile.mkdtemp(prefix="cottas_app_")
        st.session_state["temp_dir"] = temp_dir
        atexit.register(_cleanup, temp_dir)
    return st.session_state["temp_dir"]


def _cleanup(path: str) -> None:
    """Elimina el directorio temporal al finalizar el proceso."""
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def save_upload(uploaded_file, suffix: str = "") -> str:
    """
    Guarda un UploadedFile de Streamlit en el directorio temporal.

    Returns
    -------
    str
        Ruta absoluta al fichero guardado.
    """
    temp_dir = init_session_dir()
    if not suffix:
        suffix = os.path.splitext(uploaded_file.name)[1] or ".bin"
    fd, path = tempfile.mkstemp(suffix=suffix, dir=temp_dir)
    with os.fdopen(fd, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return path


def persist_uploaded_file(uploaded_file, state_key: str, suffix: str = "") -> str | None:
    """Guarda un upload una sola vez por contenido y lo reutiliza en reruns.

    Parameters
    ----------
    uploaded_file:
        UploadedFile de Streamlit o ``None``.
    state_key:
        Clave base en ``st.session_state`` donde se guarda la ruta persistida.
    suffix:
        Extensión forzada del fichero guardado.
    """
    if uploaded_file is None:
        st.session_state.pop(state_key, None)
        st.session_state.pop(f"{state_key}__sig", None)
        st.session_state.pop(f"{state_key}__name", None)
        return None

    raw = uploaded_file.getvalue()
    signature = hashlib.sha1(raw).hexdigest()
    if (
        st.session_state.get(f"{state_key}__sig") == signature
        and st.session_state.get(state_key)
        and os.path.exists(st.session_state[state_key])
    ):
        return st.session_state[state_key]

    path = save_upload(uploaded_file, suffix=suffix)
    st.session_state[state_key] = path
    st.session_state[f"{state_key}__sig"] = signature
    st.session_state[f"{state_key}__name"] = uploaded_file.name
    return path


def temp_path(filename: str) -> str:
    """Devuelve una ruta dentro del directorio temporal de la sesión."""
    temp_dir = init_session_dir()
    return os.path.join(temp_dir, filename)


def read_bytes(path: str) -> bytes:
    """Lee un fichero y devuelve sus bytes."""
    with open(path, "rb") as f:
        return f.read()


def file_size_mb(path: str) -> float:
    """Tamaño de un fichero en MB."""
    return os.path.getsize(path) / (1024 ** 2)


def file_exists(path: str) -> bool:
    return os.path.isfile(path)
