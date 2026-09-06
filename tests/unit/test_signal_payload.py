"""Testes US4 — Payload JSON §3.11.

Independent Test:
- Schema/campos obrigatórios do exemplo §3.11
- meia_vida_minutos = meia_vida_barras × 30
- validade_ate coerente com meia-vida
- NEUTRO não inventa direção LONG/SHORT

Reference: Espec F5 US4
"""

from __future__ import annotations

import json
import math
import pytest
from datetime import datetime, timezone, timedelta

from motor.signal.payload import (
    PayloadMotor,
    SinalQuantitativo,
    EstatisticasModelo,
    RiscosEstatisticos,
    CalibracaoAdaptativa,
    criar_payload_neutro,
    montar_payload,
)


def load_payload_fixtures() -> dict:
    """Carrega fixtures de teste para payload."""
    with open("tests/fixtures/signal/payload.json") as f:
        return json.load(f)


class TestPayloadAlta:
    """Testes para payload ALTA."""
    
    def test_payload_alta_creation(self):
        """Given ALTA signal, When payload created, Then correct structure."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.85,
            confianca="ALTA",
            instrumento="PETR4",
            z_score=-1.5,
            percentil_z=0.92,
            hurst=0.35,
            tau=25.5,
            mu=0.001,
            theta=0.3,
            garch_sigma=0.015,
            omega=0.0001,
            alpha=0.08,
            beta=0.88,
            cv_theta=0.25,
        )
        
        assert payload.sinal_quantitativo.direcao == "LONG"
        assert payload.sinal_quantitativo.forca == 0.85
        assert payload.sinal_quantitativo.confianca == "ALTA"
    
    def test_payload_meia_vida_calculation(self):
        """meia_vida_minutos = tau × 30."""
        tau = 25.5
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            tau=tau,
        )
        
        assert payload.sinal_quantitativo.meia_vida_barras == tau
        assert payload.sinal_quantitativo.meia_vida_minutos == tau * 30


class TestPayloadMedia:
    """Testes para payload MÉDIA."""
    
    def test_payload_media_creation(self):
        """Given MÉDIA signal, When payload created, Then correct structure."""
        payload = montar_payload(
            direcao="SHORT",
            forca=0.68,
            confianca="MÉDIA",
            instrumento="BBDC4",
            z_score=1.2,
            percentil_z=0.75,
            tau=18.0,
        )
        
        assert payload.sinal_quantitativo.direcao == "SHORT"
        assert payload.sinal_quantitativo.forca == 0.68
        assert payload.sinal_quantitativo.confianca == "MÉDIA"


class TestPayloadNeutro:
    """Testes para payload NEUTRO."""
    
    def test_payload_neutro_creation(self):
        """When 8.6 abort, payload has direcao/confianca = NEUTRO."""
        payload = criar_payload_neutro(
            instrumento="PETR4",
            candle_contexto={"reason": "skewness extrema"},
            filtros_passados=["8.6_abort"],
            evidencias=["Skewness extrema → NEUTRO"],
        )
        
        assert payload.sinal_quantitativo.direcao == "NEUTRO"
        assert payload.sinal_quantitativo.confianca == "NEUTRO"
        assert payload.sinal_quantitativo.forca == 0.0
    
    def test_neutro_no_long_short_direction(self):
        """NEUTRO payload não inventa LONG/SHORT direction."""
        payload = criar_payload_neutro(instrumento="TEST")
        
        # A direção não deve ser LONG ou SHORT
        assert payload.sinal_quantitativo.direcao != "LONG"
        assert payload.sinal_quantitativo.direcao != "SHORT"
    
    def test_neutro_validacao_ate_null(self):
        """NEUTRO payload sem validade."""
        payload = criar_payload_neutro()
        
        # NEUTRO não deve ter validade até
        assert payload.sinal_quantitativo.validade_ate is None or payload.sinal_quantitativo.validade_ate == ""


class TestMeiaVida:
    """Testes para cálculo de meia-vida."""
    
    def test_meia_vida_minutos_calculation(self):
        """meia_vida_minutos = meia_vida_barras × 30."""
        tau_values = [10.0, 25.5, 50.0, 100.0]
        
        for tau in tau_values:
            payload = montar_payload(
                direcao="LONG",
                forca=0.75,
                confianca="ALTA",
                instrumento="TEST",
                tau=tau,
            )
            
            assert payload.sinal_quantitativo.meia_vida_barras == tau
            assert payload.sinal_quantitativo.meia_vida_minutos == tau * 30


class TestValidadeAte:
    """Testes para validade até."""
    
    def test_validade_ate_present(self):
        """validade_ate está presente quando tau é fornecido."""
        tau = 50.0  # 1500 minutos = 25 horas
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            tau=tau,
        )
        
        assert payload.sinal_quantitativo.validade_ate is not None
        assert payload.sinal_quantitativo.validade_ate != ""
    
    def test_validade_ate_calculation(self):
        """validade_ate é calculada corretamente a partir de tau."""
        tau = 10.0  # 300 minutos
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            tau=tau,
        )
        
        # Validade deve ser aproximadamente tau * 30 minutos à frente
        assert payload.sinal_quantitativo.validade_ate is not None
        if payload.sinal_quantitativo.validade_ate:
            validade = datetime.fromisoformat(payload.sinal_quantitativo.validade_ate.replace('Z', '+00:00'))
            expected_validade = datetime.now(timezone.utc) + timedelta(minutes=tau * 30)
            
            # Diferença deve ser menor que 1 minuto (tolerância)
            diff = abs((validade - expected_validade).total_seconds())
            assert diff < 60


class TestPayloadSchema:
    """Testes para schema obrigatório do payload."""
    
    def test_has_versao_protocolo(self):
        """Payload tem versão_protocolo."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            tau=10.0,
        )
        
        assert hasattr(payload, 'versao_protocolo')
        assert payload.versao_protocolo == "F5.0"
    
    def test_has_timestamp_geracao(self):
        """Payload tem timestamp_geracao."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            tau=10.0,
        )
        
        assert hasattr(payload, 'timestamp_geracao')
        # Deve ser ISO format
        if payload.timestamp_geracao:
            datetime.fromisoformat(payload.timestamp_geracao.replace('Z', '+00:00'))
    
    def test_has_origem(self):
        """Payload tem origem."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            tau=10.0,
        )
        
        assert hasattr(payload, 'origem')
        assert payload.origem == "motor"
    
    def test_has_instrumento(self):
        """Payload tem instrumento."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="PETR4",
            tau=10.0,
        )
        
        assert hasattr(payload, 'instrumento')
        assert payload.instrumento == "PETR4"
    
    def test_has_sinal_quantitativo(self):
        """Payload tem sinal_quantitativo."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            tau=10.0,
        )
        
        assert hasattr(payload, 'sinal_quantitativo')
        sq = payload.sinal_quantitativo
        assert hasattr(sq, 'direcao')
        assert hasattr(sq, 'forca')
        assert hasattr(sq, 'confianca')
        assert hasattr(sq, 'meia_vida_minutos')
        assert hasattr(sq, 'validade_ate')
    
    def test_has_estatisticas_modelo(self):
        """Payload tem estatisticas_modelo."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            mu=0.001,
            theta=0.3,
            garch_sigma=0.015,
            tau=10.0,
        )
        
        assert hasattr(payload, 'estatisticas_modelo')
        sm = payload.estatisticas_modelo
        assert hasattr(sm, 'mu_t')
        assert hasattr(sm, 'theta')
        assert hasattr(sm, 'garch_sigma')
    
    def test_has_filtros_passados(self):
        """Payload tem filtros_passados."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            tau=10.0,
        )
        
        assert hasattr(payload, 'filtros_passados')
        assert isinstance(payload.filtros_passados, list)
    
    def test_has_candle_contexto(self):
        """Payload tem candle_contexto."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            tau=10.0,
        )
        
        assert hasattr(payload, 'candle_contexto')
        assert isinstance(payload.candle_contexto, dict)
    
    def test_has_evidencias(self):
        """Payload tem evidencias."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            tau=10.0,
        )
        
        assert hasattr(payload, 'evidencias')
        assert isinstance(payload.evidencias, list)
    
    def test_has_riscos_estatisticos(self):
        """Payload tem riscos_estatisticos."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            tau=10.0,
        )
        
        assert hasattr(payload, 'riscos_estatisticos')
        re = payload.riscos_estatisticos
        assert hasattr(re, 'forca_penalizada')
        assert hasattr(re, 'cv_theta_alto')
        assert hasattr(re, 'reversao_confirmada')
        assert hasattr(re, 'skewness_extrema')
    
    def test_has_calibracao_adaptativa(self):
        """Payload tem calibracao_adaptativa (placeholder)."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.75,
            confianca="ALTA",
            instrumento="TEST",
            tau=10.0,
        )
        
        assert hasattr(payload, 'calibracao_adaptativa')
        ca = payload.calibracao_adaptativa
        assert hasattr(ca, 'threshold_adaptativo')
        assert hasattr(ca, 'trigger_rate_2sem')


class TestPayloadSerialization:
    """Testes para serialização do payload."""
    
    def test_to_dict(self):
        """Payload pode ser convertido para dicionário."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.85,
            confianca="ALTA",
            instrumento="PETR4",
            z_score=-1.5,
            percentil_z=0.92,
            tau=25.0,
        )
        
        d = payload.to_dict()
        
        assert isinstance(d, dict)
        assert d['versao_protocolo'] == "F5.0"
        assert d['sinal_quantitativo']['direcao'] == "LONG"
        assert d['sinal_quantitativo']['confianca'] == "ALTA"
    
    def test_to_json(self):
        """Payload pode ser convertido para JSON."""
        payload = montar_payload(
            direcao="LONG",
            forca=0.85,
            confianca="ALTA",
            instrumento="PETR4",
            tau=25.0,
        )
        
        json_str = payload.to_json()
        
        assert isinstance(json_str, str)
        
        # Pode ser parseado como JSON
        parsed = json.loads(json_str)
        assert parsed['sinal_quantitativo']['direcao'] == "LONG"


class TestPayloadFixtures:
    """Testes usando fixtures de payload.json."""
    
    def test_alta_fixture(self):
        """Testa fixture de payload ALTA."""
        fixture = load_payload_fixtures()
        
        for case in fixture["test_cases"]:
            if case["name"] == "payload_alta":
                expected = case["expected"]
                
                payload = montar_payload(
                    direcao=case["direcao"],
                    forca=case["forca"],
                    confianca=case["confianca"],
                    instrumento=case["instrumento"],
                    z_score=case["z_score"],
                    percentil_z=case["percentil_z"],
                    hurst=case["hurst"],
                    tau=case["tau"],
                    mu=case["mu"],
                    theta=case["theta"],
                    garch_sigma=case["garch_sigma"],
                    omega=case["omega"],
                    alpha=case["alpha"],
                    beta=case["beta"],
                    cv_theta=case["cv_theta"],
                )
                
                assert payload.versao_protocolo == expected["versao_protocolo"]
                assert payload.sinal_quantitativo.forca == expected["sinal_forca"]
    
    def test_neutro_fixture(self):
        """Testa fixture de payload NEUTRO."""
        fixture = load_payload_fixtures()
        
        for case in fixture["test_cases"]:
            if case["name"] == "payload_neutro":
                payload = criar_payload_neutro()
                
                assert payload.sinal_quantitativo.direcao == "NEUTRO"
                assert payload.sinal_quantitativo.confianca == "NEUTRO"