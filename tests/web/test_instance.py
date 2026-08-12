"""tz_web.instance — instancia única, metadata y recuperación de bloqueos
obsoletos (MICROBLOQUE 5, AUD-02).

El lock real usa ``msvcrt.locking()``: dos ``InstanceLock`` distintos sobre
el mismo ``run_dir`` (aquí, dos objetos en el mismo proceso, cada uno con su
propio descriptor de archivo) ya reproducen fielmente "otro proceso tiene el
lock", porque Windows aplica el bloqueo por *handle*, no por proceso — es
exactamente el mecanismo que hace que un crash libere el lock solo, sin que
nadie tenga que limpiar nada.
"""

from __future__ import annotations

import os

import pytest

from tz_web import instance


def _metadata(**overrides) -> instance.InstanceMetadata:
    base = dict(
        schema_version=instance.INSTANCE_SCHEMA_VERSION,
        instance_id="instance-aaa",
        pid=os.getpid(),
        port=54321,
        token="secreto-token",
        created_at=1000.0,
        app_version="1.1",
        launcher_version=instance.LAUNCHER_VERSION,
    )
    base.update(overrides)
    return instance.InstanceMetadata(**base)


@pytest.fixture()
def run_dir(tmp_path):
    d = tmp_path / "run"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# 1. Primera instancia crea metadata válida.
# ---------------------------------------------------------------------------


def test_primera_instancia_crea_metadata_valida(run_dir):
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True
    lock.write_metadata(_metadata())

    reloaded = instance.InstanceLock(run_dir).read_metadata()
    assert reloaded is not None
    assert reloaded.instance_id == "instance-aaa"
    assert reloaded.port == 54321
    assert reloaded.token == "secreto-token"
    lock.release()


# ---------------------------------------------------------------------------
# 2/3. Segunda ejecución detecta instancia válida y no inicia un segundo
# backend (el plan resultante es "reuse", nunca "start").
# ---------------------------------------------------------------------------


def test_segunda_ejecucion_detecta_instancia_valida_y_no_arranca_otra(run_dir):
    holder = instance.InstanceLock(run_dir)
    assert holder.try_acquire() is True
    meta = _metadata()
    holder.write_metadata(meta)

    second = instance.InstanceLock(run_dir)

    def fake_health(port, token):
        assert port == meta.port
        assert token == meta.token
        return {"instance_id": meta.instance_id}

    plan = instance.resolve_startup_plan(second, health_checker=fake_health, sleep=lambda _s: None)
    assert plan.action == "reuse"
    assert plan.metadata.instance_id == meta.instance_id
    holder.release()


# ---------------------------------------------------------------------------
# 4/16. Metadata stale (proceso muerto) se recupera automáticamente: el
# lock queda libre porque el SO lo liberó, sin inspeccionar PID ni edad de
# archivo.
# ---------------------------------------------------------------------------


def test_metadata_stale_permite_nuevo_arranque_tras_liberar_el_lock(run_dir):
    crashed = instance.InstanceLock(run_dir)
    assert crashed.try_acquire() is True
    crashed.write_metadata(_metadata(instance_id="instancia-vieja"))
    # Simula la muerte del proceso: el SO libera el handle solo.
    crashed.release()

    fresh = instance.InstanceLock(run_dir)
    plan = instance.resolve_startup_plan(fresh)
    assert plan.action == "start"
    assert plan.metadata is None
    fresh.release()


# ---------------------------------------------------------------------------
# 5. PID reciclado / instancia que no responde a health no se acepta como
# válida (nunca se fuerza el lock ni se asume que el PID sigue vivo).
# ---------------------------------------------------------------------------


def test_instancia_sin_health_no_se_acepta_como_valida(run_dir):
    holder = instance.InstanceLock(run_dir)
    assert holder.try_acquire() is True
    holder.write_metadata(_metadata())

    second = instance.InstanceLock(run_dir)
    plan = instance.resolve_startup_plan(
        second, health_checker=lambda port, token: None, retries=2, sleep=lambda _s: None
    )
    assert plan.action == "blocked"
    assert plan.reason == "stale_or_foreign"
    holder.release()


# ---------------------------------------------------------------------------
# 6. Puerto ocupado por un proceso ajeno (responde, pero no es esta
# instancia) tampoco se acepta.
# ---------------------------------------------------------------------------


def test_puerto_ocupado_por_proceso_ajeno_no_se_acepta(run_dir):
    holder = instance.InstanceLock(run_dir)
    assert holder.try_acquire() is True
    holder.write_metadata(_metadata(instance_id="instancia-real"))

    second = instance.InstanceLock(run_dir)
    plan = instance.resolve_startup_plan(
        second,
        health_checker=lambda port, token: {"instance_id": "otra-app-cualquiera"},
        retries=1,
        sleep=lambda _s: None,
    )
    assert plan.action == "blocked"
    assert plan.reason == "instance_id_mismatch"
    holder.release()


# ---------------------------------------------------------------------------
# 7. Metadata ilegible mientras el lock sigue tomado -> bloqueado (no se
# arranca un segundo backend a ciegas).
# ---------------------------------------------------------------------------


def test_metadata_ilegible_con_lock_tomado_queda_bloqueado(run_dir):
    holder = instance.InstanceLock(run_dir)
    assert holder.try_acquire() is True
    # No se escribe metadata: el archivo no existe.

    second = instance.InstanceLock(run_dir)
    plan = instance.resolve_startup_plan(second)
    assert plan.action == "blocked"
    assert plan.reason == "metadata_unreadable"
    holder.release()


# ---------------------------------------------------------------------------
# 15. El cierre limpio solo borra la metadata mientras el lock sigue en
# manos de quien la escribió; una instancia nueva parte de cero.
# ---------------------------------------------------------------------------


def test_release_borra_solo_la_metadata_propia(run_dir):
    first = instance.InstanceLock(run_dir)
    assert first.try_acquire() is True
    first.write_metadata(_metadata(instance_id="primera"))
    first.release()
    assert not (run_dir / "instance.json").exists()

    second = instance.InstanceLock(run_dir)
    assert second.try_acquire() is True
    second.write_metadata(_metadata(instance_id="segunda"))
    reloaded = instance.InstanceLock(run_dir).read_metadata()
    assert reloaded.instance_id == "segunda"
    second.release()


# ---------------------------------------------------------------------------
# Token nunca queda completo en una representación pensada para logs.
# ---------------------------------------------------------------------------


def test_log_safe_dict_nunca_expone_el_token_completo():
    meta = _metadata(token="token-super-secreto-1234567890")
    safe = meta.log_safe_dict()
    assert safe["token"] != meta.token
    assert meta.token not in str(safe)


def test_metadata_redonda_por_json(run_dir):
    lock = instance.InstanceLock(run_dir)
    assert lock.try_acquire() is True
    original = _metadata()
    lock.write_metadata(original)
    reloaded = instance.InstanceLock(run_dir).read_metadata()
    assert reloaded == original
    lock.release()
