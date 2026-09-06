"""Bootstrap Moving Block de θ para medir estabilidade (F3).

Implementa Moving Block Bootstrap conforme spec §3.6.

Especificação detalhada:
- Input: X (série de log-preços, janela 200), não lista de θs
- Block bootstrap: l=20, N=100 réplicas
- Cada réplica: concat de blocos de X com reposição, truncar a 200
- Cada réplica: mesmo estimate OU de ou.py → θ_b
- IC_low = percentile(θ_b, 2.5%)
- n_bootstrap < 100 ou < 10 θ_b finitos → IC indefinido → NEUTRO
- Proibido: choice iid ponto a ponto; ruído 1% no escalar.

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
    ic_low: Optional[float] = None  # IC inferior (percentil 2.5%)
    n_valid_samples: int = 0  # Número de θ_b finitos
    n_bootstrap: int = 100  # Número de réplicas
    seed: int = 42
    reason: Optional[str] = None


class BootstrapTheta:
    """Moving Block Bootstrap para estimativa de θ."""
    
    WINDOW_SIZE = 200
    N_BOOTSTRAP = 100  # Número de réplicas
    CV_THRESHOLD = 0.30
    MU_THRESHOLD = 0.05  # μ_θ ≈ 0 considerado neutro (5% de margem)
    SEED = 42
    IC_PERCENTILE = 2.5  # Percentil inferior 95% CI
    BLOCK_LENGTH = 20  # l = 20 barras
    
    def __init__(self, X: List[float], n_bootstrap: int = 100, seed: int = 42):
        """Inicializa o bootstrap.
        
        Args:
            X: Série de log-preços (janela 200)
            n_bootstrap: Número de réplicas (default 100)
            seed: Seed para reproducibilidade
        """
        self.X = np.array(X, dtype=np.float64)
        self.n_bootstrap = n_bootstrap
        self.seed = seed
        self.window_size = self.WINDOW_SIZE
        
    def _estimate_theta(self, series: np.ndarray) -> float:
        """Estima θ usando OLS discretizado.
        
        Fórmula: X_t = mu + exp(-theta) * (X_{t-1} - mu) + noise
        De onde: b = exp(-theta), a = mu * (1 - b)
        
        Args:
            series: Série de log-preços (200 pontos)
            
        Returns:
            Estimativa de theta
        """
        if len(series) < 10:
            return 0.0
        
        n = len(series)
        X_lag = series[:-1]
        X_curr = series[1:]
        
        # Estimativas via OLS
        X_mean = np.mean(series)
        
        # Covariância e correlação
        cov_X = np.cov(X_lag, X_curr)[0, 1]
        var_X_lag = np.var(X_lag)
        
        if var_X_lag == 0 or np.isnan(var_X_lag):
            return 0.0
        
        b = cov_X / var_X_lag  # exp(-theta)
        
        # Verificar se b está no domínio válido
        if b <= 0 or b >= 1:
            return 0.0
        
        # Extrair theta
        try:
            theta = -np.log(b)
        except (ValueError, RuntimeWarning):
            return 0.0
        
        if not np.isfinite(theta):
            return 0.0
            
        return theta
    
    def _moving_block_bootstrap(self) -> List[float]:
        """Realiza Moving Block Bootstrap.
        
        Algoritmo:
        1. Dividir X em blocos de tamanho l=20
        2. Para cada réplica:
           a. Escolher blocos com reposição
           b. Concatenar blocos
           c. Truncar para tamanho janela (200)
           d. Estimar θ
        
        Returns:
            Lista de estimativas de theta (θ_b)
        """
        rng = np.random.default_rng(self.seed)
        
        # Dividir X em blocos de tamanho l=20
        l = self.BLOCK_LENGTH
        n_blocks = len(self.X) // l
        
        if n_blocks == 0:
            return []
        
        blocks = []
        for i in range(n_blocks):
            block = self.X[i * l:(i + 1) * l]
            if len(block) == l:
                blocks.append(block)
        
        if len(blocks) == 0:
            return []
        
        # Gerar réplicas
        theta_samples = []
        
        for _ in range(self.n_bootstrap):
            # Escolher blocos com reposição
            n_needed = (self.WINDOW_SIZE // l) + 1
            selected_indices = rng.choice(len(blocks), size=n_needed, replace=True)
            
            # Concatenar blocos
            replica = np.concatenate([blocks[i] for i in selected_indices])
            
            # Truncar para tamanho janela
            replica = replica[:self.WINDOW_SIZE]
            
            if len(replica) < 10:
                continue
            
            # Estimar theta
            theta = self._estimate_theta(replica)
            
            if np.isfinite(theta):
                theta_samples.append(float(theta))
        
        return theta_samples
    
    def run(self) -> BootstrapResult:
        """Executa bootstrap e calcula IC.
        
        Returns:
            BootstrapResult com CV, IC_low e flags
        """
        # Verificar se X tem tamanho suficiente
        if len(self.X) < self.WINDOW_SIZE:
            return BootstrapResult(
                status=BootstrapStatus.NEUTRO,
                reason="Series too short",
                seed=self.seed,
                n_bootstrap=self.n_bootstrap
            )
        
        # Extrair janela final X_{t-199:t}
        X_window = self.X[-self.WINDOW_SIZE:]
        
        # Executar moving block bootstrap
        theta_samples = self._moving_block_bootstrap()
        n_valid = len(theta_samples)
        
        # n_bootstrap < 100 ou < 10 θ_b finitos → IC indefinido → NEUTRO
        if self.n_bootstrap < 100 or n_valid < 10:
            return BootstrapResult(
                status=BootstrapStatus.NEUTRO,
                theta_samples=theta_samples if theta_samples else None,
                mu_theta=0.0,
                sigma_theta=0.0,
                cv_theta=None,
                is_stable=False,
                forca_penalty_cv=False,
                ic_low=None,  # IC indefinido
                n_valid_samples=n_valid,
                seed=self.seed,
                n_bootstrap=self.n_bootstrap
            )
        
        # Calcular estatísticas
        theta_array = np.array(theta_samples)
        mu_theta = float(np.mean(theta_array))
        sigma_theta = float(np.std(theta_array, ddof=0))
        
        # IC_low = percentile(θ_b, 2.5%)
        ic_low = float(np.percentile(theta_samples, self.IC_PERCENTILE))
        
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
                theta_samples=theta_samples,
                mu_theta=mu_theta,
                sigma_theta=sigma_theta,
                cv_theta=None,
                is_stable=False,
                forca_penalty_cv=False,
                ic_low=ic_low,
                n_valid_samples=n_valid,
                seed=self.seed,
                n_bootstrap=self.n_bootstrap
            )
        
        # Verificar IC_low <= 0 → NEUTRO
        if ic_low <= 0:
            return BootstrapResult(
                status=BootstrapStatus.NEUTRO,
                theta_samples=theta_samples,
                mu_theta=mu_theta,
                sigma_theta=sigma_theta,
                cv_theta=cv_theta,
                is_stable=False,
                forca_penalty_cv=cv_theta > self.CV_THRESHOLD if cv_theta else False,
                ic_low=ic_low,
                n_valid_samples=n_valid,
                seed=self.seed,
                n_bootstrap=self.n_bootstrap
            )
        
        # CV > 0.30 → marca penalização mas continua
        if cv_theta is not None and cv_theta > self.CV_THRESHOLD:
            return BootstrapResult(
                status=BootstrapStatus.PASS,
                theta_samples=theta_samples,
                mu_theta=mu_theta,
                sigma_theta=sigma_theta,
                cv_theta=cv_theta,
                is_stable=False,
                forca_penalty_cv=True,
                ic_low=ic_low,
                n_valid_samples=n_valid,
                seed=self.seed,
                n_bootstrap=self.n_bootstrap
            )
        
        # CV <= 0.30 → estável
        return BootstrapResult(
            status=BootstrapStatus.PASS,
            theta_samples=theta_samples,
            mu_theta=mu_theta,
            sigma_theta=sigma_theta,
            cv_theta=cv_theta,
            is_stable=True,
            forca_penalty_cv=False,
            ic_low=ic_low,
            n_valid_samples=n_valid,
            seed=self.seed,
            n_bootstrap=self.n_bootstrap
        )


def bootstrap_theta(X: List[float], n_bootstrap: int = 100, seed: int = 42) -> BootstrapResult:
    """Executa Moving Block Bootstrap para θ.
    
    Args:
        X: Série de log-preços (janela 200)
        n_bootstrap: Número de réplicas (default 100)
        seed: Seed para reproducibilidade (default 42)
        
    Returns:
        BootstrapResult com CV, IC_low e flags
    """
    boot = BootstrapTheta(X, n_bootstrap, seed)
    return boot.run()