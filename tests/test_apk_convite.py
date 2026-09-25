"""APK do Track One embutido no convite.

O wa.me só leva texto, então o APK vai como link de download dentro da
mensagem. Se isso quebrar calado, o técnico recebe um convite que promete o
app e não entrega — e trava logo no primeiro passo do piloto.
"""
import io

import pytest

from app import models
from app.database import SessionLocal

APK_FALSO = b"PK\x03\x04" + b"\x00" * 64


@pytest.fixture(autouse=True)
def sem_apk():
    yield
    db = SessionLocal()
    try:
        db.query(models.InstaladorApp).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _sobe_apk(client, conteudo=APK_FALSO, nome="track-one-1.4.0.apk"):
    return client.post("/api/tecnicos/apk", files={"file": (nome, io.BytesIO(conteudo), "application/octet-stream")})


def test_sem_apk_convite_continua_prometendo_o_link(client, tecnico):
    assert client.get("/api/tecnicos/apk").json() is None
    msg = client.get(f"/api/tecnicos/{tecnico['id']}/mensagem").json()
    assert msg["apk_link"] is None
    assert "(o link será enviado a seguir)" in msg["mensagem"]


def test_convite_leva_o_link_do_apk_dentro_da_mensagem(client, tecnico):
    assert _sobe_apk(client).status_code == 201

    msg = client.get(f"/api/tecnicos/{tecnico['id']}/mensagem").json()
    assert msg["apk_link"].endswith("/app/track-one.apk")
    assert msg["apk_link"] in msg["mensagem"]
    assert "(o link será enviado a seguir)" not in msg["mensagem"]
    # o link do WhatsApp carrega o mesmo texto, já com o APK
    assert "track-one.apk" in msg["wa_link"]

    acionamento = client.get(f"/api/tecnicos/{tecnico['id']}/mensagem?tipo=acionamento").json()
    assert msg["apk_link"] in acionamento["mensagem"]


def test_link_do_apk_baixa_o_arquivo(client):
    _sobe_apk(client)
    resp = client.get("/app/track-one.apk")
    assert resp.status_code == 200
    assert resp.content == APK_FALSO
    assert resp.headers["content-type"] == "application/vnd.android.package-archive"
    assert "track-one.apk" in resp.headers["content-disposition"]


def test_apk_novo_substitui_o_anterior_no_mesmo_link(client):
    _sobe_apk(client, nome="v1.apk")
    novo = APK_FALSO + b"v2"
    assert _sobe_apk(client, conteudo=novo, nome="v2.apk").json()["filename"] == "v2.apk"
    assert client.get("/app/track-one.apk").content == novo


def test_so_aceita_apk(client):
    assert _sobe_apk(client, nome="manual.pdf").status_code == 400
    assert _sobe_apk(client, conteudo=b"nao sou zip").status_code == 400
    assert client.get("/app/track-one.apk").status_code == 404


def test_lider_nao_recebe_apk_e_cobranca_so_para_quem_nao_instalou(client, tecnico):
    _sobe_apk(client)
    lider = client.post("/api/tecnicos", json={
        "nome": "Marcos Líder", "telefone": "11977776666", "papel": "lider",
    }).json()
    assert client.get(f"/api/tecnicos/{lider['id']}/mensagem").json()["apk_link"] not in \
        client.get(f"/api/tecnicos/{lider['id']}/mensagem").json()["mensagem"]

    client.patch(f"/api/tecnicos/{tecnico['id']}", json={"status": "convidado"})
    cobranca = client.get(f"/api/tecnicos/{tecnico['id']}/mensagem?tipo=cobranca").json()
    assert cobranca["apk_link"] in cobranca["mensagem"]

    client.patch(f"/api/tecnicos/{tecnico['id']}", json={"status": "instalado"})
    cobranca = client.get(f"/api/tecnicos/{tecnico['id']}/mensagem?tipo=cobranca").json()
    assert cobranca["apk_link"] not in cobranca["mensagem"]


def test_remover_apk_volta_a_promessa(client, tecnico):
    _sobe_apk(client)
    assert client.delete("/api/tecnicos/apk").json() == {"deleted": 1}
    assert "(o link será enviado a seguir)" in client.get(f"/api/tecnicos/{tecnico['id']}/mensagem").json()["mensagem"]
