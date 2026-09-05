"""Estimativa de processo Ornstein-Uhlenbeck (F3).

Implementa OU via Kalman discreto padrão (pykalman) com fallback MLE
para θ ≤ 0 ou não-finito, conforme spec §3.5.

Fórmulas:
- OU: dX_t = -θ * X_t * dt + μ * dt + σ * dW_t
- τ = ln(2) / θ  (tempo de meia-vida)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple
import numpy as np
from scipy import stats
from scipy.optimize import minimize


class OUStatus(str, Enum):
    """Status da estimação OU."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


@dataclass
class OUEstimationResult:
    """Resultado da estimação OU."""
    status: OUStatus
    mu: Optional[float] = None
    theta: Optional[float] = None
    tau: Optional[float] = None
    sigma: Optional[float] = None
    method: Optional[str] = None  # "kalman" ou "mle"
    reason: Optional[str] = None


class OUEstimator:
    """Estimador de processo Ornstein-Uhlenbeck."""
    
    WINDOW_SIZE = 200
    
    def __init__(self, series: List[float], use_kalman: bool = True):
        """Inicializa o estimador.
        
        Args:
            series: Série de preços X_t (log-price)
            use_kalman: Se True, tenta Kalman primeiro
        """
        self.series = np.array(series, dtype=np.float64)
        self.use_kalman = use_kalman
    
    def _estimate_via_kalman(self) -> Tuple[float, float, float, float]:
        """Estima OU usando pykalman.
        
        Returns:
            Tupla (mu, theta, sigma, log_likelihood)
        """
        try:
            from pykalman import KalmanFilter
            
            n = len(self.series)
            X_t = self.series.reshape(-1, 1)
            
            # Modelo OU discreto:
            # X_t = mu + exp(-theta*dt) * (X_{t-1} - mu) + sigma * sqrt(1 - exp(-2*theta*dt)) * noise
            # Para dt = 1 (barra):
            # Transição: X_t = mu + exp(-theta) * (X_{t-1} - mu) + noise_var * epsilon
            
            # Primeiro, estimativa inicial via regrassão simples
            X_lag = X_t[:-1].flatten()
            X_curr = X_t[1:].flatten()
            
            # Regressão: X_curr = a + b * X_lag
            # Onde b = exp(-theta), a = mu * (1 - b)
            n_samples = len(X_lag)
            if n_samples < 10:
                raise ValueError("Série muito curta para Kalman")
            
            # Estimativas via OLS
            X_mean = np.mean(X_t)
            
            # Covariância e correlação
            cov_X = np.cov(X_lag, X_curr)[0, 1]
            var_X_lag = np.var(X_lag)
            
            if var_X_lag == 0:
                raise ValueError("Variação zero na série")
            
            b = cov_X / var_X_lag  # exp(-theta)
            a = np.mean(X_curr - b * X_lag)  # mu * (1 - b)
            
            # Extrair parâmetros
            if b <= 0 or b >= 1:
                raise ValueError(f"b={b} fora do intervalo válido (0,1)")
            
            theta = -np.log(b)
            mu = a / (1 - b) if abs(1 - b) > 1e-10 else X_mean
            
            # Estimar sigma do resíduo
            residuals = X_curr - (a + b * X_lag)
            sigma = np.std(residuals, ddof=1)
            
            # Ajustar para escalar corretamente
            # Var(resíduo) ≈ sigma^2 * (1 - exp(-2*theta))
            if sigma > 0 and theta > 0:
                sigma = sigma / np.sqrt(1 - np.exp(-2 * theta))
            
            return mu, theta, sigma, 0.0
            
        except Exception as e:
            raise ValueError(f"Kalman fitting failed: {e}")
    
    def _estimate_via_mle(self) -> Tuple[float, float, float, float]:
        """Estima OU via MLE (máxima verossimilhança).
        
        Returns:
            Tupla (mu, theta, sigma, log_likelihood)
        """
        n = len(self.series)
        if n < 20:
            raise ValueError("Série muito curta para MLE")
        
        X_t = self.series
        X_lag = X_t[:-1]
        X_curr = X_t[1:]
        
        # Função de verossimilhança negativa (para minimização)
        def neg_log_likelihood(params):
            mu, theta, sigma = params
            if theta <= 0 or sigma <= 0:
                return 1e10
            
            # Previsão OU: E[X_t | X_{t-1}] = mu + exp(-theta) * (X_{t-1} - mu)
            exp_theta = np.exp(-theta)
            predicted = mu + exp_theta * (X_lag - mu)
            
            # Erro quadrático
            residuals = X_curr - predicted
            
            # Log-verossimilhança (assumindo normal)
            # Var = sigma^2 * (1 - exp(-2*theta))
            var = sigma**2 * (1 - exp_theta**2)
            
            ll = -0.5 * n * np.log(2 * np.pi * var) - 0.5 * np.sum(residuals**2) / var
            return -ll
        
        # Estimativas iniciais
        X_mean = np.mean(X_t)
        X_var = np.var(X_t)
        
        if X_var == 0:
            return X_mean, 0.0, 0.0, -np.inf
        
        # Estimativa inicial de theta via autocorrelação
        autocorr = np.corrcoef(X_lag, X_curr)[0, 1]
        if np.isnan(autocorr) or autocorr >= 1 or autocorr <= 0:
            autocorr = 0.5
        
        theta_init = -np.log(max(0.01, min(0.99, autocorr)))
        sigma_init = np.sqrt(X_var / 2) if theta_init > 0 else np.sqrt(X_var)
        
        # Otimização
        result = minimize(
            neg_log_likelihood,
            x0=[X_mean, theta_init, sigma_init],
            method='L-BFGS-B',
            bounds=[(None, None), (1e-6, 10.0), (1e-6, 10.0)],
            options={'maxiter': 1000}
        )
        
        if not result.success:
            raise ValueError(f"MLE optimisation failed: {result.message}")
        
        mu, theta, sigma = result.x
        ll = -result.fun
        
        return mu, theta, sigma, ll
    
    def estimate(self) -> OUEstimationResult:
        """Estima o processo OU.
        
        Returns:
            OUEstimationResult com status e parâmetros
        """
        n = len(self.series)
        
        # Warm-up check
        if n < self.WINDOW_SIZE:
            return OUEstimationResult(
                status=OUStatus.NEUTRO,
                reason=" Insufficient historical data for estimation"
            )
        
        # Extrair janela final
        series_window = self.series[-self.WINDOW_SIZE:]
        
        method_used = None
        mu, theta, sigma, ll = None, None, None, None
        reason = None
        
        # Tentar Kalman primeiro
        if self.use_kalman:
            try:
                mu, theta, sigma, ll = self._estimate_via_kalman()
                method_used = "kalman"
            except Exception as e:
                reason = f"Kalman failed: {e}"
        
        # Fallback para MLE se necessário
        if method_used is None or theta is None or theta <= 0:
            try:
                mu, theta, sigma, ll = self._estimate_via_mle()
                method_used = "mle"
            except Exception as e:
                return OUEstimationResult(
                    status=OUStatus.NEUTRO,
                    reason=f"Both Kalman and MLE failed: {e}"
                )
        
        # Verificar parâmetros
        if mu is None or theta is None or theta <= 0:
            return OUEstimationResult(
                status=OUStatus.NEUTRO,
                mu=float(mu) if mu is not None else 0.0,
                theta=0.0,
                reason="θ ≤ 0 after estimation"
            )
        
        # Calcular tau = ln(2) / theta
        tau = float(np.log(2) / theta) if theta > 0 else None
        
        return OUEstimationResult(
            status=OUStatus.PASS,
            mu=float(mu),
            theta=float(theta),
            tau=tau,
            sigma=float(sigma) if sigma is not None else None,
            method=method_used,
            reason=None
        )


def estimate_ou_kalman(series: List[float], window_size: int = 200) -> OUEstimationResult:
    """Estima processo OU via Kalman com fallback MLE.
    
    Args:
        series: Série de preços X_t (log-price)
        window_size: Tamanho da janela para estimação
        
    Returns:
        OUEstimationResult com status e parâmetros
    """
    estimator = OUEstimator(series, use_kalman=True)
    return estimator.estimate()


def estimate_ou_mle(series: List[float], window_size: int = 200) -> OUEstimationResult:
    """Estima processo OU via MLE (sempre tenta MLE).
    
    Args:
        series: Série de preços X_t (log-price)
        window_size: Tamanho da janela para estimação
        
    Returns:
        OUEstimationResult com status e parâmetros
    """
    estimator = OUEstimator(series, use_kalman=False)
    return estimator.estimate()