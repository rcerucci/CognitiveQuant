"""Bootstrap de θ para medir estabilidade (F3).

Implementa bootstrap IID com 50 reamostragens para calcular CV = σ_θ / μ_θ
conforme spec §3.6.

Regras:
- CV ≤ 0.30 → θ estável
- CV > 0.30 → flag forca_penalty_cv sem NEUTRO
- μ_θ ≈ 0 → NEUTRO
- IC_low (p2.5%) > 0 → elegível para PASS
- seed = 42
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import numpy as np


class BootstrapStatus(str, Enum):
    """Status do bootstrap."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


@dataclass
class BootstrapResult:
    """Resultado do bootstrap de θ."""
    status: BootstrapStatus
    theta_samples: Optional[List[float]] = None
    mu_theta: Optional[float] = None
    sigma_theta: Optional[float] = None
    cv_theta: Optional[float] = None
    is_stable: Optional[bool] = None
    forca_penalty_cv: bool = False
    ic_low: Optional[float] = None  # Percentil 2.5% das samples
    seed: int = 42


class BootstrapTheta:
    """Bootstrap para estimativa de θ."""
    
    WINDOW_SIZE = 200
    N_BOOTSTRAP = 50
    CV_THRESHOLD = 0.30
    MU_THRESHOLD = 0.05  # μ_θ ≈ 0 considerado neutro (5% de margem)
    SEED = 42
    IC_PERCENTILE = 2.5  # Percentil inferior 95% CI
    
    def __init__(self, thetas: List[float], n_bootstrap: int = None, seed: int = None):
        """Inicializa o bootstrap.
        
        Args:
            thetas: Lista de estimativas de θ (ou vetor de θs)
            n_bootstrap: Número de reamostragens (default 50)
            seed: Seed para reproducibilidade
        """
        self.thetas = np.array(thetas, dtype=np.float64)
        self.n_bootstrap = n_bootstrap or self.N_BOOTSTRAP
        self.seed = seed if seed is not None else self.SEED
    
    def run(self) -> BootstrapResult:
        """Executa bootstrap IID e calcula CV.
        
        Returns:
            BootstrapResult com CV, IC e flags
        """
        # Usar seed para reproducibilidade
        rng = np.random.default_rng(self.seed)
        
        # Casos edge
        if len(self.thetas) == 0:
            return BootstrapResult(
                status=BootstrapStatus.NEUTRO,
                theta_samples=[],
                mu_theta=0.0,
                sigma_theta=0.0,
                cv_theta=None,
                is_stable=False,
                ic_low=0.0
            )
        
        # Se apenas um θ, não faz sentido bootstrap
        if len(self.thetas) == 1:
            theta = float(self.thetas[0])
            if theta <= 0:
                return BootstrapResult(
                    status=BootstrapStatus.NEUTRO,
                    theta_samples=[theta],
                    mu_theta=theta,
                    sigma_theta=0.0,
                    cv_theta=0.0,
                    is_stable=True,
                    forca_penalty_cv=False,
                    ic_low=theta
                )
            return BootstrapResult(
                status=BootstrapStatus.PASS,
                theta_samples=[theta],
                mu_theta=theta,
                sigma_theta=0.0,
                cv_theta=0.0,
                is_stable=True,
                forca_penalty_cv=False,
                ic_low=theta
            )
        
        # Calcular estatísticas diretamente dos thetas originais
        # CV = σ_θ / μ_θ
        mu_theta = float(np.mean(self.thetas))
        sigma_theta = float(np.std(self.thetas, ddof=0))
        
        # Bootstrap IID: gerar samples para cálculo de IC
        bootstrap_thetas = []
        for _ in range(self.n_bootstrap):
            # Amostrar com substituição para gerar theta de bootstrap
            sample_indices = rng.choice(len(self.thetas), size=len(self.thetas), replace=True)
            sample = self.thetas[sample_indices]
            bootstrap_thetas.append(float(np.mean(sample)))
        
        # Calcular IC inferior (percentil 2.5%)
        ic_low = float(np.percentile(bootstrap_thetas, self.IC_PERCENTILE))
        
        # CV = σ_θ / μ_θ
        if abs(mu_theta) > self.MU_THRESHOLD:
            cv_theta = float(sigma_theta / abs(mu_theta))
        else:
            cv_theta = None  # Indefinido quando μ_θ ≈ 0
        
        # Verificar estabilidade
        is_stable = cv_theta is not None and cv_theta <= self.CV_THRESHOLD
        
        # Verificar μ_θ ≈ 0 → NEUTRO
        if abs(mu_theta) < self.MU_THRESHOLD:
            return BootstrapResult(
                status=BootstrapStatus.NEUTRO,
                theta_samples=bootstrap_thetas,
                mu_theta=mu_theta,
                sigma_theta=sigma_theta,
                cv_theta=None,
                is_stable=False,
                ic_low=ic_low,
                forca_penalty_cv=False
            )
        
        # Verificar IC_low ≤ 0 → NEUTRO (T033)
        if ic_low <= 0:
            return BootstrapResult(
                status=BootstrapStatus.NEUTRO,
                theta_samples=bootstrap_thetas,
                mu_theta=mu_theta,
                sigma_theta=sigma_theta,
                cv_theta=cv_theta,
                is_stable=False,
                ic_low=ic_low,
                forca_penalty_cv=cv_theta > self.CV_THRESHOLD if cv_theta else False
            )
        
        # CV > 0.30 → marca penalização mas continua
        if cv_theta is not None and cv_theta > self.CV_THRESHOLD:
            return BootstrapResult(
                status=BootstrapStatus.PASS,
                theta_samples=bootstrap_thetas,
                mu_theta=mu_theta,
                sigma_theta=sigma_theta,
                cv_theta=cv_theta,
                is_stable=False,
                ic_low=ic_low,
                forca_penalty_cv=True
            )
        
        # CV ≤ 0.30 → estável
        return BootstrapResult(
            status=BootstrapStatus.PASS,
            theta_samples=bootstrap_thetas,
            mu_theta=mu_theta,
            sigma_theta=sigma_theta,
            cv_theta=cv_theta,
            is_stable=True,
            ic_low=ic_low,
            forca_penalty_cv=False
        )


def bootstrap_theta(thetas: List[float], n_bootstrap: int = 50, seed: int = 42) -> BootstrapResult:
    """Executa bootstrap IID para θ.
    
    Args:
        thetas: Lista de estimativas de θ
        n_bootstrap: Número de reamostragens (default 50)
        seed: Seed para reproducibilidade (default 42)
        
    Returns:
        BootstrapResult com CV e flags
    """
    boot = BootstrapTheta(thetas, n_bootstrap, seed)
    return boot.run()