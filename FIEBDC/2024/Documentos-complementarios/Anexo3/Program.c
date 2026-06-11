#define STRICT
#include <windows.h>
#include <stdio.h>
#include <conio.h>
#include "Program.h"

int main (void) {

	/*	COMENTARIO 1														*/
	/*	MODIFIQUE LAS SIGUIENTES VARIABLE SI DESEA UTILIZAR ESTE PROGRAMA	*/
	/*	EJEMPLO PARA VERIFICAR OTRA BASE CON PARAMÉTRICOS EN DLL			*/
	char		*nBase="BASE.DLL";
	char		*nSalida="SALIDA.TXT";
	char		*Precios [] = {"ABPH.1$", "SBRG.1$", "EADR.3$", "Esp$", "NoExiste"};
	long		nPrecios = 5;
	char		*Secciones [] = {"NOR"};
	long		nSecciones = 1;
	/*	FIN DEL COMENTARIO 1												*/

	HANDLE		Precio=(HANDLE)0, PrecioTmp=(HANDLE)0;
	HINSTANCE	hLib=(HINSTANCE)0;
	FILE		*fSalida;
	char		*err, codigo[NMAX_COD+1];
	const char	*texto;
	long		i,j,k;
	long		limite,nParGlobales=0,nPar,codificacion,TipoPliego;
	long		nOpc[NMAX_PAR],ListaOpc[NMAX_PAR],ListaOpc2[NMAX_PAR],ListaOpcGlobales[NMAX_PAR];
	double		numero;
	long		nValidos,iValido;
	BYTE		*cValidos;

	printf ("\nEJEMPLO DE PROGRAMA QUE ACCEDE A LA BASE \"%s\"\n",nBase);
	printf ("LOS RESULTADOS SE ESCRIBEN EN EL ARCHIVO \"%s\"\n",nSalida);
	printf ("(c) Asociacion FIEBDC\n");

	if ( !(fSalida = fopen (nSalida, "wt")) ) {
		printf ("\nERROR: Imposible crear el archivo de salida\n");
		printf ("\n\nPROGRAMA FINALIZADO\nPulse una tecla\n");
		getch();
		return FALSE;
	}
	fprintf (fSalida,"\nEJEMPLO DE PROGRAMA QUE ACCEDE A LA BASE \"%s\"\n",nBase);
	fprintf (fSalida,"(c) Asociación FIEBDC\n");

	if (!AbreDll(nBase, &hLib, &err)) {
		fprintf (fSalida,"\nERROR: %s\n", err);
		printf ("\n\nPROGRAMA FINALIZADO\nPulse una tecla\n");
		getch();
		fcloseall();
		return FALSE;
	} else if (err[0]!=0)
		fprintf (fSalida,"\nERROR: %s\n", err);

	/*Tipo de Codificación*/
	codificacion=pCodificacion();
	switch (codificacion) {
		case 0:	fprintf (fSalida, "\nLa codificación es dependiente de los parámetros"); break;
		case 1:	fprintf (fSalida, "\nLa codificación es independiente de los parámetros"); break;
		default: fprintf (fSalida, "\nBdcCodificación devuelve un valor erróneo (%ld)",codificacion); codificacion=0;
	}

	/*Tipo de Textos de Pliego*/
	TipoPliego=pTipoPliego();
	switch (TipoPliego) {
		case 0: fprintf (fSalida, "\nNo existen textos de Pliego en la Base\n"); break;
		case 1: fprintf (fSalida, "\nLos Pliegos siguen el modelo uno\n"); break;
		case 2: fprintf (fSalida, "\nLos Pliegos siguen el modelo dos\n"); break;
		case 3: fprintf (fSalida, "\nLos Pliegos siguen los modelos uno y dos\n"); break;
		default: fprintf (fSalida, "\nBdcTipoPliego devuelve un valor erróneo (%ld)",TipoPliego); TipoPliego=0;
	}

	/*Lectura del Paramétrico Global*/
	printf ("\nBUSCANDO EL PARAMETRICO GLOBAL...");
	fprintf (fSalida,"\n========================================================");
	nParGlobales = pGloParNumero();
	if (nParGlobales>0)
		printf ("\nLEYENDO EL PARAMETRICO GLOBAL...");
	if (nParGlobales==ERRONEO)
		ChequeaError ((HANDLE)0, fSalida, TRUE);
	else if (nParGlobales == 0)
		fprintf (fSalida,"\nNo existe un Paramétrico Global\n");
	else {
		fprintf (fSalida,"\nPrecio Global: Número de parámetros: %ld\n", nParGlobales);
		for (j=0; j<nParGlobales; j++) {
			ListaOpcGlobales[j]=0;
			if (!(texto=pGloParRotulo(j)))
				ChequeaError ((HANDLE)0, fSalida, TRUE);
			else
				fprintf (fSalida,"\nParámetro %ld: Rótulo: %s\n", j, texto);
			limite=pGloOpcNumero(j);
			if (limite==ERRONEO)
				ChequeaError ((HANDLE)0, fSalida, TRUE);
			for (k=0; k<limite; k++) {
				if (!(texto=pGloOpcRotulo(j,k)))
					ChequeaError ((HANDLE)0, fSalida, TRUE);
				else
					fprintf (fSalida,"\tOpción %ld: Rótulo: %s\n", k, texto);
			}
		}
	}
	if (nParGlobales>0) pGloCalcula (ListaOpcGlobales);
	
	/*Lectura de los precios*/
	for (i=0; i<nPrecios; i++) {
		printf ("\n\nBUSCANDO EL PRECIO \"%s\"...", Precios[i]);
		fprintf (fSalida,"\n========================================================");
		if ( (Precio = pLee (Precios[i])) == (HANDLE) 0 ) {
			fprintf (fSalida,"\nERROR: El precio \"%s\" no existe\n", Precios[i]);
			continue;
		}

		/*Rótulos de Parámetros y Opciones*/
		printf ("\nLEYENDO EL PRECIO \"%s\"...", Precios[i]);
		nPar = pParNumero(Precio);
		if (nPar==ERRONEO)
			ChequeaError (Precio, fSalida, FALSE);
		else
			fprintf (fSalida,"\nPrecio \"%s\": Número de parámetros: %ld\n", Precios[i], nPar);
		for (j=0; j<nPar; j++) {
			if (!(texto=pParRotulo(Precio,j)))
				ChequeaError (Precio, fSalida, FALSE);
			else
				fprintf (fSalida,"\nParámetro %ld: Rótulo: %s\n", j, texto);
			nOpc[j]=pOpcNumero(Precio,j);
			if (nOpc[j]==ERRONEO)
				ChequeaError (Precio, fSalida, FALSE);
			ListaOpc[j]=0;
			for (k=0; k<nOpc[j]; k++) {
				if (!(texto=pOpcRotulo(Precio,j,k)))
					ChequeaError (Precio, fSalida, FALSE);
				else
					fprintf (fSalida,"\tOpción %ld: Rótulo: %s\n", k, texto);
			}
		}

		if (!(texto=pComentario(Precio)))
			ChequeaError (Precio, fSalida, FALSE);
		else
			fprintf (fSalida,"COMENTARIO: %s\n", texto);

		/*Listado de todas las combinaciones paramétricas*/
		printf ("\nCALCULANDO EL PRECIO \"%s\"...", Precios[i]);
		/*Combinaciones Válidas*/
		nValidos=pValidos(Precio,&cValidos);
		if (nValidos) {
			fprintf (fSalida,"\nExisten %d combinaciones válidas",nValidos);
			iValido=0;
			for (j=0; j<nPar; j++) {
				ListaOpc[j] = (long)(cValidos[(iValido*nPar)+j]);
			}
		}
		for(;;) {
			if (nPar>0) {
				fprintf (fSalida,"\n--------------------------------------------------------");
				if (pValida (Precio, ListaOpc)!=CORRECTO) {
					fprintf (fSalida,"\n");
					ChequeaError (Precio, fSalida, FALSE);
					fprintf (fSalida,"(CODIGO : %s)\n", pCodigo(Precio));
					goto siguiente;
				}
			}
			pCalcula (Precio, ListaOpc);
			if (!(texto=pCodigo(Precio))) {
				ChequeaError (Precio, fSalida, FALSE);
				sprintf (codigo,"");
			} else
				strcpy (codigo, texto);
			fprintf (fSalida,"\nCODIGO: %s\n", codigo);
			
			/*Comprobación: obtención de las opciones a partir del derivado*/
			if (nPar>0 && strlen(codigo)) {
				if (codificacion) {
					if ((PrecioTmp=pDecodifica (codigo, ListaOpc2)) == (HANDLE)0) {
						fprintf (fSalida, "\nAl llamar a BdcDecodifica ocurrió el siguiente ");
						ChequeaError (PrecioTmp, fSalida, FALSE);
					} else {
						pCierra (PrecioTmp);
						fprintf (fSalida,"OPCIONES: ");
						for (j=0; j<nPar; j++) {
							fprintf (fSalida,"%ld ",ListaOpc2[j]);
							if (ListaOpc[j] != ListaOpc2[j]) {
								break; /*NO hay concordancia*/
							}
						}
						if (j<nPar)
							fprintf (fSalida,"BdcDecodifica no devolvió correctamente esta opción");
					}
				} else {
					fprintf (fSalida,"OPCIONES: ");
					for (j=0; j<nPar; j++) {
						if		(codigo[j+6]>='a' && codigo[j+6]<='z') ListaOpc2[j]=codigo[j+6]-'a';
						else if	(codigo[j+6]>='A' && codigo[j+6]<='Z') ListaOpc2[j]=26+codigo[j+6]-'A';
						else if	(codigo[j+6]>='0' && codigo[j+6]<='9') ListaOpc2[j]=52+codigo[j+6]-'0';
						else	ListaOpc2[j]=-1; /*error*/
						fprintf (fSalida,"%ld ",ListaOpc2[j]);
					}
				}
			}

			if (!(texto=pUnidad(Precio)))
				ChequeaError (Precio, fSalida, FALSE);
			else
				fprintf (fSalida,"\nUNIDAD:%s\n", texto);
			if (!(texto=pResumen(Precio)))
				ChequeaError (Precio, fSalida, FALSE);
			else
				fprintf (fSalida,"RESUMEN:%s\n", texto);
			if (!(texto=pTexto(Precio)))
				ChequeaError (Precio, fSalida, FALSE);
			else
				fprintf (fSalida,"TEXTO:%s\n", texto);
			
			/*Pliego según modelo uno*/
			if (TipoPliego & 0x01) {
				for (j=0;j<nSecciones;j++) {
					if (!(texto=pPliego(Precio,BDCFMT_ASCII,BDCPLI_DERIVADO,Secciones[j],"")))
						ChequeaError (Precio, fSalida, FALSE);
					else
						fprintf (fSalida,"PLIEGO: (SECCION %s) %s\n", Secciones[j],texto);
				}
			}

			/*Pliego según modelo dos*/
			if (TipoPliego & 0x02) {
				for (j=0;j<nSecciones;j++) {
					if (!(texto=pCodParrafo(Precio,BDCPLI_DERIVADO,Secciones[j],"")))
						ChequeaError (Precio, fSalida, FALSE);
					else
						fprintf (fSalida,"PÁRRAFOS DEL PLIEGO: (SECCION %s) %s\n", Secciones[j],texto);
				}
			}

			limite=pDesNumero(Precio);
			if (limite==ERRONEO)
				ChequeaError (Precio, fSalida, FALSE);
			else if (limite) {
				fprintf (fSalida,"DESCOMPOSICION:\n");
				for (j=0; j<limite; j++) {
					if (!(texto=pDesCodigo(Precio,j)))
						ChequeaError (Precio, fSalida, FALSE);
					else if (pRendimiento(Precio,j,&numero)==ERRONEO)
						ChequeaError (Precio, fSalida, FALSE);
					else
						fprintf (fSalida,"\t%2ld %-10s \t%10.3lf\n", j+1, texto, numero);
				}
			} else {
				if (pPrecio(Precio, &numero)==ERRONEO)
					ChequeaError (Precio, fSalida, FALSE);
				else
					fprintf (fSalida,"PRECIO:%.2lf\n", numero);
			}

siguiente:			
			if (nValidos) {
				//Siguiente concepto derivado válido
				iValido++;
				if (iValido>=nValidos) break;
				for (j=0; j<nPar; j++) {
					ListaOpc[j] = (long)(cValidos[(iValido*nPar)+j]);
				}
			} else {
				//Siguiente derivado
				for (j=nPar-1; j>=0; j--) {
					if (ListaOpc[j]<nOpc[j]-1) {
						ListaOpc[j]++;
						break;
					} else {
						ListaOpc[j]=0;
					}
				}
				if (j<0) break;
			}
		}

		pCierra (Precio);
	}

	if (!CierraDll ((HMODULE)hLib, &err) ) {
		fprintf (fSalida,"\nERROR: %s\n", err);
		printf ("\n\nPROGRAMA FINALIZADO\nPulse una tecla\n");
		getch();
		return FALSE;
	}
	printf ("\n\nPROGRAMA FINALIZADO\nPulse una tecla\n");
	getch();

	fcloseall();

	return TRUE;
}
